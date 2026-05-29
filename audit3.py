"""Final audit: parse models and tools lists."""
import urllib.request, json

BASE = "http://localhost:8080"
token = urllib.request.urlopen(urllib.request.Request(
    f"{BASE}/api/v1/auths/signin",
    data=json.dumps({"email": "aaron@slothitude.com", "password": "Sloth2026!"}).encode(),
    headers={"Content-Type": "application/json"}
))
token = json.loads(token.read().decode())["token"]

def get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers={"Authorization": f"Bearer {token}"})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())

# Models (trailing slash returns HTML, no slash returns JSON)
models = get("/api/v1/models")
data = models.get("data", [])
print(f"MODELS: {len(data)} total")
custom = [m for m in data if m.get("connection_type") != "external"]
external = [m for m in data if m.get("connection_type") == "external"]
print(f"  Custom models: {len(custom)}")
for m in custom:
    base = m.get("base_model_id", "")
    has_prompt = bool(m.get("params", {}).get("system_prompt"))
    print(f"    - {m['id']} (base: {base}, prompt: {has_prompt})")
print(f"  External (LiteLLM): {len(external)}")
local = [m for m in external if not m["id"].startswith(("nim-", "or-", "zai-"))]
print(f"    Local favorites: {[m['id'] for m in local]}")

# Tools
tools = get("/api/v1/tools/")
print(f"\nTOOLS: {len(tools)} installed")
for t in tools:
    name = t.get("name", t["id"])
    desc = t.get("meta", {}).get("description", "")
    print(f"  - {name}: {desc}")

# Terminal
print(f"\nTERMINAL:")
ts = get("/api/v1/configs/terminal_servers")
for c in ts.get("TERMINAL_SERVER_CONNECTIONS", []):
    print(f"  - {c['name']} @ {c['url']} (enabled: {c['enabled']})")

# Check agent model has tools enabled
print(f"\nAGENT MODEL CHECK:")
for m in custom:
    if "agent" in m["id"].lower():
        print(f"  ID: {m['id']}")
        print(f"  Base: {m.get('base_model_id', 'none')}")
        print(f"  Has system prompt: {bool(m.get('params', {}).get('system_prompt'))}")
        meta = m.get("meta", {})
        caps = meta.get("capabilities", {})
        print(f"  Capabilities: {caps}")
