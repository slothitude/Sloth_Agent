"""Chat with Sloth Agent via OpenWebUI API.

Usage:
  python agent_chat.py "search for today's news"     # send message, wait for response
  python agent_chat.py --read                         # read latest chat history
  python agent_chat.py --chats                        # list all chats
"""
import sys
import time
import uuid
import json
import re
import urllib.request
import urllib.error

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE = "http://192.168.0.33:3000"
MODEL = "sloth-agent"
EMAIL = "aaron@slothitude.com"
PASSWORD = "Sloth2026!"
POLL_INTERVAL = 3
MAX_POLL = 300  # 5 minutes


def get_token():
    req = urllib.request.Request(
        f"{BASE}/api/v1/auths/signin",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())["token"]


def api(method, path, token, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:500]
        print(f"API error {e.code}: {err}", file=sys.stderr)
        return None


def strip_reasoning(text):
    """Remove <details> reasoning blocks from response."""
    return re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL).strip()


def send_message(token, message, chat_id=None):
    """Send a message and get the response."""
    msg_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    body = {
        "chat_id": chat_id or "",
        "id": msg_id,
        "messages": [{"role": "user", "content": message}],
        "model": MODEL,
        "stream": False,
        "session_id": session_id,
    }

    print(f"Sending: {message}")
    result = api("POST", "/api/chat/completions", token, body)
    if not result:
        print("Failed to send message", file=sys.stderr)
        sys.exit(1)

    choices = result.get("choices", [])
    if not choices:
        print(f"No response choices. Raw: {json.dumps(result)[:500]}")
        return None

    msg = choices[0].get("message", {})
    content = msg.get("content", "")
    reasoning = msg.get("reasoning_content", "")
    tool_calls = msg.get("tool_calls", [])

    clean = strip_reasoning(content)
    print(f"\nAgent: {clean}")

    if reasoning:
        print(f"\n[Reasoning: {reasoning[:300]}...]")

    if tool_calls:
        print(f"\n[Tool calls: {len(tool_calls)}]")
        for tc in tool_calls:
            fn = tc.get("function", {}).get("name", "?")
            args = tc.get("function", {}).get("arguments", "")[:200]
            print(f"  - {fn}: {args}")

    resp_id = result.get("id", "")
    print(f"\n(Response ID: {resp_id})")
    return resp_id


def read_chat(token, chat_id=None):
    """Read and display chat history."""
    if chat_id:
        chats = [{"id": chat_id}]
    else:
        result = api("GET", "/api/v1/chats/?page=0", token)
        if not result:
            print("No chats found", file=sys.stderr)
            return
        chats = result
        if not chats:
            print("No chats found")
            return
        # Use the most recent chat
        chats = [chats[0]]
        print(f"Latest chat: {chats[0].get('title', 'untitled')}")

    for c in chats:
        cid = c["id"]
        chat = api("GET", f"/api/v1/chats/{cid}", token)
        if not chat:
            continue

        title = chat.get("title", "untitled")
        print(f"\n{'='*60}")
        print(f"Chat: {title} ({cid})")
        print(f"{'='*60}")

        messages = chat.get("history", {}).get("messages", {})
        # Sort by timestamp
        sorted_msgs = sorted(messages.values(), key=lambda m: m.get("timestamp", 0))

        for msg in sorted_msgs:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            done = msg.get("done", True)

            if role == "user":
                print(f"\n[USER] {content[:500]}")
            elif role == "assistant":
                clean = strip_reasoning(content)
                status = "" if done else " (incomplete)"
                print(f"\n[AGENT{status}] {clean[:1000]}")

                # Show tool calls if any
                tc = msg.get("tool_calls") or msg.get("metadata", {}).get("tool_calls")
                if tc:
                    for t in tc:
                        fn = t.get("function", {}).get("name", "?")
                        print(f"  [TOOL] {fn}")


def list_chats(token):
    """List all chats."""
    result = api("GET", "/api/v1/chats/?page=0", token)
    if not result:
        print("No chats found")
        return

    for i, chat in enumerate(result):
        cid = chat.get("id", "?")
        title = chat.get("title", "untitled")
        updated = chat.get("updated_at", 0)
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(updated / 1000)) if updated else "?"
        print(f"  {i+1}. [{ts}] {title}  ({cid[:12]}...)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    token = get_token()

    if sys.argv[1] == "--chats":
        list_chats(token)
    elif sys.argv[1] == "--read":
        chat_id = sys.argv[2] if len(sys.argv) > 2 else None
        read_chat(token, chat_id)
    else:
        message = " ".join(sys.argv[1:])
        chat_id = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith("--chat=") else None
        if chat_id:
            chat_id = chat_id.split("=", 1)[1]
        send_message(token, message, chat_id)


if __name__ == "__main__":
    main()
