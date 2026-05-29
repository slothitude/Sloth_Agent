"""Fix Agent model: create as workspace model with system prompt + function calling."""
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

# 1. Check if old agent model exists in workspace and delete it
models = api("GET", "/api/v1/models", token)
existing_ids = [m["id"] for m in models.get("data", [])]
print(f"Existing model IDs containing 'agent': {[m for m in existing_ids if 'agent' in m.lower()]}")

# Delete old agent model if it exists as a workspace model
for m in models.get("data", []):
    if m["id"] == "agent" and m.get("connection_type") != "external":
        print(f"  Deleting old workspace model: {m['id']}")
        api("DELETE", f"/api/v1/models/{m['id']}", token)

# 2. List available base models (from LiteLLM + Ollama)
print("\nAvailable base models (top picks for tool calling):")
picks = ["zai-glm-5-turbo", "zai-ant-glm-5-turbo", "qwen3.5", "gemma4", "glm4"]
for p in picks:
    found = p in existing_ids
    print(f"  {'[x]' if found else '[ ]'} {p}")

# 3. Create the Agent workspace model
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

# Try creating with the proper API format for v0.9.5
result = api("POST", "/api/v1/models/create", token, {
    "id": "agent",
    "name": "Agent",
    "base_model_id": "zai-glm-5-turbo",
    "meta": {
        "profile_image_url": "",
        "description": "Full agent with terminal, file access, web search, and custom tools. Uses GLM-5 Turbo via Z.ai.",
    },
    "params": {
        "system_prompt": agent_prompt,
        "temperature": None,
    },
    "access_control": None,
    "is_active": True,
})
print(f"\nCreate result: {json.dumps(result, indent=2)[:500]}")

if "error" in result:
    # Try alternate endpoint
    print("\nTrying /api/v1/models/add ...")
    result = api("POST", "/api/v1/models/add", token, {
        "id": "agent",
        "name": "Agent",
        "base_model_id": "zai-glm-5-turbo",
        "meta": {
            "description": "Full agent with terminal, file access, web search, and custom tools.",
        },
        "params": {
            "system_prompt": agent_prompt,
        },
        "access_control": None,
    })
    print(f"Add result: {json.dumps(result, indent=2)[:500]}")

# 4. Verify - get the model back and check
if "error" not in result:
    model_id = result.get("id", "agent")
    check = api("GET", f"/api/v1/models/{model_id}", token)
    if "error" not in check:
        print(f"\nVerified model: {check.get('id')}")
        print(f"  base_model_id: {check.get('base_model_id')}")
        print(f"  has system_prompt: {bool(check.get('params', {}).get('system_prompt'))}")
        print(f"  prompt length: {len(check.get('params', {}).get('system_prompt', ''))}")
    else:
        print(f"\nVerify failed: {check}")

print("\n=== Agent model fix complete ===")
