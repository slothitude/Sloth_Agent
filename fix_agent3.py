"""Create agent model with unique ID."""
import urllib.request, json

BASE = "http://localhost:8080"

def get_token():
    req = urllib.request.Request(
        f"{BASE}/api/v1/auths/signin",
        data=json.dumps({"email": "aaron@slothitude.com", "password": "Sloth2026!"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())["token"]

def api(method, path, token, data=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode() if data else None,
        headers=headers,
        method=method
    )
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()
        return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:500]}

token = get_token()

agent_prompt = """You are an autonomous AI agent with access to a terminal, file system, and web search.

You can execute commands, read and write files, search code, and browse the web.
Think step by step. When you need information, run a command. When you need to
change something, edit the file. When you're done, summarize what you did.

## Tools Available
- **Terminal**: Execute any shell command (bash, python, node, etc.)
- **File Browser**: Read, write, list, search files
- **Code Execution**: Run Python, Node.js, etc.
- **Web Search**: Search the internet for current information
- **URL Fetcher**: Fetch and read web pages
- **Memory**: Save and recall information across conversations
- **Git Tools**: Status, diff, log
- **Docker Manager**: List, logs, restart containers

## Rules
1. Always read a file before editing it
2. Run tests after making changes
3. Use grep/search to understand code before modifying
4. Explain what you're doing before each tool call
5. If a command fails, read the error and fix it - do not give up
6. Keep responses concise - show output, don't narrate it
7. Stay inside the working directory of the current task
8. Use the Web Search tool when you need current information
9. Use Memory tool to save important findings for later"""

# Use "sloth-agent" as the ID to avoid collision with LiteLLM's "agent"
result = api("POST", "/api/v1/models/create", token, {
    "id": "sloth-agent",
    "name": "Sloth Agent",
    "base_model_id": "zai-glm-5-turbo",
    "meta": {
        "description": "Full agent with terminal, file access, web search, and custom tools. Uses GLM-5 Turbo.",
    },
    "params": {
        "system_prompt": agent_prompt,
    },
    "access_control": None,
    "is_active": True,
})

if "error" not in result:
    print(f"SUCCESS")
    print(f"  ID: {result.get('id')}")
    print(f"  Name: {result.get('name')}")
    print(f"  Base: {result.get('base_model_id')}")
    print(f"  Has prompt: {bool(result.get('params', {}).get('system_prompt'))}")
    print(f"  Prompt length: {len(result.get('params', {}).get('system_prompt', ''))}")
else:
    print(f"FAILED: {result}")
