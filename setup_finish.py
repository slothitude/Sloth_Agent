"""Fix Phase 2 & 3: correct API formats."""
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
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:500]}

token = get_token()

# Fix models config - DEFAULT_MODELS is a string, not a list
result = api("POST", "/api/v1/configs/models", token, {
    "DEFAULT_MODELS": "zai-glm-5-turbo",  # default model
    "DEFAULT_PINNED_MODELS": [],
    "MODEL_ORDER_LIST": [],
    "MODEL_RATE_LIMIT": "",
    "ENABLE_MODEL_FILTER": False,
    "MODEL_FILTER_LIST": [],
    "DEFAULT_MODEL_METADATA": {},
    "DEFAULT_MODEL_PARAMS": {}
})
print(f"1. Models config: {'ok' if 'error' not in result else str(result)[:200]}")

# Fix connections config
result = api("POST", "/api/v1/configs/connections", token, {
    "ENABLE_DIRECT_CONNECTIONS": True,
    "OPENAI_API_BASE_URLS": ["http://192.168.0.33:4000/v1"],
    "OPENAI_API_KEYS": ["sk-litellm-b15241627ba17201797f1446b25d82a9"],
    "OPENAI_API_CONFIGS": {}
})
print(f"2. Connections: {'ok' if 'error' not in result else str(result)[:200]}")

# Create Agent model via the correct endpoint
# Models are created via /api/v1/models/create
result = api("POST", "/api/v1/models/create", token, {
    "id": "agent",
    "name": "Agent",
    "base_model_id": "zai-glm-5-turbo",
    "meta": {
        "profile_image_url": "",
        "description": "Full agent with terminal access - uses GLM-5 Turbo",
        "capabilities": {"native_function_calling": True}
    },
    "params": {
        "system_prompt": """You are an autonomous AI agent with access to a terminal, file system, and web search.

You can execute commands, read and write files, search code, and browse the web.
Think step by step. When you need information, run a command. When you need to
change something, edit the file. When you're done, summarize what you did.

## Tools Available
- **Terminal**: Execute any shell command (bash, python, node, etc.)
- **File Browser**: Read, write, list, search files
- **Code Execution**: Run Python, Node.js, etc.
- **Web Search**: Search the internet for current information

## Rules
1. Always read a file before editing it
2. Run tests after making changes
3. Use grep/search to understand code before modifying
4. Explain what you're doing before each tool call
5. If a command fails, read the error and fix it - do not give up
6. Keep responses concise - show output, don't narrate it
7. Stay inside the working directory of the current task"""
    },
    "access_control": None
})
print(f"3. Agent model: {json.dumps(result, indent=2)[:400]}")

# Verify - list models
result = api("GET", "/api/v1/models/", token)
if isinstance(result, list):
    print(f"\n4. Models available: {len(result)}")
    for m in result:
        name = m.get("name", m.get("id", "?"))
        print(f"  - {name}")
else:
    print(f"4. Models list: {str(result)[:200]}")

print("\n=== Setup complete ===")
