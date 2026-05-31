"""Sloth Engine — Z.ai GLM-5.1 streaming client."""

from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

from config import ZAI_API_KEY, ZAI_BASE_URL, DEFAULT_MODEL, MAX_TOOL_ROUNDS

# Accumulated tool calls during a streaming response
ToolCallItem = dict  # {"id": str, "type": str, "function": {"name": str, "arguments": str}}


async def stream_zai(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
) -> AsyncGenerator[dict, None]:
    """Stream from Z.ai API. Yields dicts:
    - {"type": "token", "content": "..."}
    - {"type": "thinking", "content": "..."}
    - {"type": "tool_calls", "calls": [...]}
    - {"type": "done", "reason": "..."}
    - {"type": "error", "content": "..."}
    """
    headers = {
        "Authorization": f"Bearer {ZAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15)) as client:
            async with client.stream("POST", f"{ZAI_BASE_URL}/chat/completions",
                                     headers=headers, json=payload) as resp:
                resp.raise_for_status()
                accumulated_tool_calls: dict[int, ToolCallItem] = {}

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        if accumulated_tool_calls:
                            yield {
                                "type": "tool_calls",
                                "calls": list(accumulated_tool_calls.values()),
                            }
                        yield {"type": "done", "reason": "stop"}
                        return

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})

                    # Content token — strip trailing newline (Z.ai sends \n per token)
                    content = delta.get("content")
                    if content:
                        yield {"type": "token", "content": content.rstrip("\n")}

                    # Reasoning/thinking token — strip trailing newline
                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        yield {"type": "thinking", "content": reasoning.rstrip("\n")}

                    # Tool calls (delta may contain partial)
                    tc_list = delta.get("tool_calls")
                    if tc_list:
                        for tc_delta in tc_list:
                            idx = tc_delta.get("index", 0)
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc_delta.get("id", ""),
                                    "type": tc_delta.get("type", "function"),
                                    "function": {"name": "", "arguments": ""},
                                }
                            acc = accumulated_tool_calls[idx]
                            if tc_delta.get("id"):
                                acc["id"] = tc_delta["id"]
                            fn = tc_delta.get("function", {})
                            if fn.get("name"):
                                acc["function"]["name"] = fn["name"]
                            if fn.get("arguments"):
                                acc["function"]["arguments"] += fn["arguments"]

                    # Finish reason
                    finish = choices[0].get("finish_reason")
                    if finish and finish != "stop":
                        if accumulated_tool_calls:
                            yield {
                                "type": "tool_calls",
                                "calls": list(accumulated_tool_calls.values()),
                            }
                        yield {"type": "done", "reason": finish}
                        return

                # Stream ended without [DONE]
                if accumulated_tool_calls:
                    yield {
                        "type": "tool_calls",
                        "calls": list(accumulated_tool_calls.values()),
                    }
                yield {"type": "done", "reason": "stop"}

    except httpx.HTTPStatusError as e:
        yield {"type": "error", "content": f"Z.ai API error {e.response.status_code}"}
    except httpx.RequestError as e:
        yield {"type": "error", "content": f"Z.ai connection error: {e}"}


async def chat_with_tools(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    dispatch_fn=None,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> AsyncGenerator[dict, None]:
    """Full tool loop. Streams tokens, executes tools, repeats.
    `dispatch_fn(name, args) -> str` executes a tool and returns result.
    """
    for round_num in range(max_rounds):
        tool_calls_received: list[ToolCallItem] = []

        async for event in stream_zai(messages, tools, model):
            if event["type"] in ("token", "thinking", "error", "done"):
                yield event
            elif event["type"] == "tool_calls":
                tool_calls_received.extend(event["calls"])

        if not tool_calls_received:
            return

        # Append ONE assistant message with ALL tool_calls
        messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls_received})

        # Execute all tool calls and append results
        for tc in tool_calls_received:
            fn = tc["function"]
            name = fn["name"]
            try:
                args = json.loads(fn["arguments"]) if fn["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
                yield {"type": "error", "content": f"Invalid JSON args for {name}: {fn['arguments'][:200]}"}

            if dispatch_fn:
                try:
                    result = await dispatch_fn(name, args)
                except Exception as e:
                    result = f"Tool error: {e}"
            else:
                result = f"No dispatch function configured"

            # Yield tool execution info (keep full result so engine can detect URLs)
            yield {"type": "tool_result", "content": f"[{name}] {str(result)[:2000]}"}

            # Append tool result message
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result),
            })

    yield {"type": "error", "content": f"Tool loop exceeded {max_rounds} rounds"}
