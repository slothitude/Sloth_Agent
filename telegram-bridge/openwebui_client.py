"""OpenWebUI HTTP client — auth + non-streaming chat."""
import json
import time
import uuid

import httpx

import config

_token = None
_token_time = 0


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


def send_chat(message: str, chat_id: str = None):
    """Send message to sloth-agent, return (text, chat_id).

    No tool_ids: OpenWebUI's REST API doesn't execute tools in
    non-streaming mode (returns tool_calls but never resolves them).
    The model answers from training data without tools.
    """
    if not chat_id:
        chat_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())

    body = {
        "chat_id": chat_id,
        "id": msg_id,
        "messages": [{"role": "user", "content": message}],
        "model": config.OPENWEBUI_MODEL,
        "stream": False,
    }

    url = f"{config.OPENWEBUI_BASE_URL}/api/chat/completions"

    try:
        content = _do_request(url, body, _headers())
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            _auth()
            content = _do_request(url, body, _headers())
        else:
            raise

    return content, chat_id


def _do_request(url, body, headers):
    """Non-streaming request. Returns content string."""
    r = httpx.post(url, json=body, headers=headers, timeout=180)
    r.raise_for_status()
    data = r.json()

    content = ""
    for choice in data.get("choices", []):
        msg = choice.get("message", {})
        c = msg.get("content")
        if c:
            content += c

    if not content.strip():
        return "(no response)"
    return content
