"""OpenWebUI HTTP client — auth + non-streaming chat with tool loop."""
import json
import time
import uuid
import datetime

import httpx

import config

_token = None
_token_time = 0

# SearXNG for web search tool execution
SEARXNG_URL = "http://host.docker.internal:8888"


def _auth():
    """Sign in and cache token."""
    global _token, _token_time
    r = httpx.post(
        f"{config.OPENWEBUI_BASE_URL}/api/v1/auths/signin",
        json={"email": config.OPENWEBUI_EMAIL, "password": config.OPENWEBUI_PASSWORD},
        timeout=15,
    )
    r.raise_for_status()
    _token = r.json()["token"]
    _token_time = time.time()
    return _token


def get_token():
    """Return cached token or re-auth."""
    if _token and (time.time() - _token_time) < 3600:
        return _token
    return _auth()


def _headers():
    return {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }


def _execute_tool(name: str, args: dict) -> str:
    """Execute a tool locally and return the result as JSON string."""
    if name == "get_current_timestamp":
        return json.dumps({"timestamp": datetime.datetime.now().isoformat()})

    if name in ("search_web", "web_search"):
        query = args.get("query", "")
        try:
            r = httpx.get(f"{SEARXNG_URL}/search",
                          params={"q": query, "format": "json"}, timeout=10)
            hits = []
            for item in r.json().get("results", [])[:5]:
                hits.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", "")[:200],
                })
            return json.dumps(hits)
        except Exception as e:
            return json.dumps({"error": str(e)})

    if name in ("fetch_url", "url_fetcher"):
        url = args.get("url", "")
        try:
            r = httpx.get(url, timeout=10, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
            return json.dumps({"url": str(r.url), "content": r.text[:3000]})
        except Exception as e:
            return json.dumps({"error": str(e)})

    return json.dumps({"error": f"tool {name} not available"})


def send_chat(message_history: list, chat_id: str = None):
    """Send message history to sloth-agent with tool loop, return (text, chat_id).

    Implements client-side tool execution: when the model returns tool_calls,
    executes them locally and feeds results back. Loops until final text.
    Max 10 rounds.
    """
    if not chat_id:
        chat_id = str(uuid.uuid4())

    messages = list(message_history)
    url = f"{config.OPENWEBUI_BASE_URL}/api/chat/completions"
    hdrs = _headers()

    for round_num in range(10):
        body = {
            "chat_id": chat_id,
            "id": str(uuid.uuid4()),
            "messages": messages,
            "model": config.OPENWEBUI_MODEL,
            "stream": False,
        }

        try:
            r = httpx.post(url, json=body, headers=hdrs, timeout=120)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                _auth()
                hdrs = _headers()
                r = httpx.post(url, json=body, headers=hdrs, timeout=120)
            else:
                raise
        r.raise_for_status()

        data = r.json()
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        finish = choice.get("finish_reason", "")

        if finish != "tool_calls" or not msg.get("tool_calls"):
            # Final response
            content = msg.get("content", "")
            if not content.strip():
                return "(no response)", chat_id
            return content, chat_id

        # Add assistant message with tool calls to history
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": msg["tool_calls"],
        })

        # Execute each tool and add results
        for tc in msg["tool_calls"]:
            fn = tc["function"]
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            result = _execute_tool(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    return "(max tool rounds reached)", chat_id
