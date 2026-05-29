"""Configure OpenWebUI: disable signup, add models, set system prompt, add tools."""
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
        return {"error": e.code, "detail": e.read().decode()[:300]}

token = get_token()
print(f"Token OK")

# ==========================================
# Phase 2: Disable signup, configure models
# ==========================================

# Disable signup now that admin is created
result = api("POST", "/api/v1/configs", token, {"ui": {"enable_signup": False}})
print(f"Signup disabled: {'ok' if 'error' not in result else result}")

# List available models from LiteLLM
result = api("GET", "/api/v1/configs/models", token)
print(f"Current models config: {json.dumps(result, indent=2)[:500]}")

# Check what models LiteLLM has
req = urllib.request.Request(
    "http://192.168.0.33:4000/v1/models",
    headers={"Authorization": "Bearer sk-litellm-b15241627ba17201797f1446b25d82a9"}
)
resp = urllib.request.urlopen(req)
models = json.loads(resp.read().decode())
model_ids = [m["id"] for m in models.get("data", [])]
print(f"\nAvailable LiteLLM models ({len(model_ids)}):")
for m in sorted(model_ids):
    print(f"  {m}")

# Set default models
model_config = {
    "MODEL_RATE_LIMIT": "",
    "ENABLE_MODEL_FILTER": False,
    "MODEL_FILTER_LIST": [],
    "DEFAULT_MODELS": sorted(model_ids)[:5] if model_ids else [],
    "MODEL_ORDER_LIST": sorted(model_ids) if model_ids else [],
    "ENABLE_DIRECT_FUNCTION_CALLING": True,
}

result = api("POST", "/api/v1/configs/models", token, model_config)
print(f"\nModels config set: {'ok' if 'error' not in result else result}")

# ==========================================
# Phase 3: System prompt as a model preset
# ==========================================

agent_prompt = """You are an autonomous AI agent with access to a terminal, file system, and web search.

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

# Create a model with the system prompt
result = api("POST", "/api/v1/models/add", token, {
    "id": "agent",
    "name": "Agent",
    "meta": {
        "profile_image_url": "/static/favicon.png",
        "description": "Full agent with terminal access"
    },
    "params": {
        "system_prompt": agent_prompt
    },
    "pipe": False
})
print(f"\nAgent model created: {json.dumps(result, indent=2)[:300]}")

# Also add a direct Ollama connection
result = api("POST", "/api/v1/configs/connections", token, {
    "OPENAI_API_BASE_URLS": ["http://192.168.0.33:4000/v1"],
    "OPENAI_API_KEYS": ["sk-litellm-b15241627ba17201797f1446b25d82a9"],
    "OPENAI_API_CONFIGS": {}
})
print(f"Connections config: {'ok' if 'error' not in result else str(result)[:200]}")

print("\n=== Phases 2 & 3 complete ===")
