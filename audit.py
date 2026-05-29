"""Audit: check everything in OpenWebUI."""
import urllib.request, json, sys

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
        return {"error": e.code, "detail": e.read().decode()[:300]}

token = get_token()
print("=" * 50)
print("OPENWEBUI AUDIT - v0.9.5")
print("=" * 50)

# 1. Version
print("\n[1] VERSION")
r = api("GET", "/api/version", token)
print(f"  Version: {r.get('version', r)}")

# 2. Users
print("\n[2] USERS")
r = api("GET", "/api/v1/users/", token)
if isinstance(r, list):
    for u in r:
        print(f"  - {u.get('email','?')} (role: {u.get('role','?')}, name: {u.get('name','?')})")
else:
    print(f"  {str(r)[:200]}")

# 3. Terminal connections
print("\n[3] TERMINAL CONNECTIONS")
r = api("GET", "/api/v1/configs/terminal_servers", token)
if isinstance(r, dict) and "error" not in r:
    conns = r.get("TERMINAL_SERVER_CONNECTIONS", [])
    print(f"  Connections: {len(conns)}")
    for c in conns:
        print(f"  - {c.get('name','?')} @ {c.get('url','?')} (enabled: {c.get('enabled')}, auth: {c.get('auth_type','?')})")
else:
    print(f"  {str(r)[:200]}")

# 4. Connections (LiteLLM, Ollama, etc.)
print("\n[4] LLM CONNECTIONS")
r = api("GET", "/api/v1/configs/connections", token)
if isinstance(r, dict) and "error" not in r:
    urls = r.get("OPENAI_API_BASE_URLS", [])
    print(f"  Direct connections: {r.get('ENABLE_DIRECT_CONNECTIONS', '?')}")
    for u in urls:
        print(f"  - {u}")
    # Check if Ollama is separately configured
    ollama = r.get("OLLAMA_API_BASE_URLS", [])
    for o in ollama:
        print(f"  - Ollama: {o}")
else:
    print(f"  {str(r)[:200]}")

# 5. Models
print("\n[5] CUSTOM MODELS")
r = api("GET", "/api/v1/models/", token)
if isinstance(r, list):
    print(f"  Custom models: {len(r)}")
    for m in r:
        base = m.get("base_model_id", "")
        name = m.get("name", m.get("id", "?"))
        has_prompt = bool(m.get("params", {}).get("system_prompt"))
        print(f"  - {name} (base: {base or 'none'}, prompt: {has_prompt})")
elif isinstance(r, dict) and "error" not in r:
    # might return paginated
    items = r.get("data", r.get("items", []))
    print(f"  Models: {len(items)}")
    for m in items:
        print(f"  - {m.get('name', m.get('id', '?'))}")
else:
    print(f"  {str(r)[:200]}")

# 6. Default model
print("\n[6] DEFAULT MODEL CONFIG")
r = api("GET", "/api/v1/configs/models", token)
if isinstance(r, dict) and "error" not in r:
    print(f"  Default model: {r.get('DEFAULT_MODELS', 'not set')}")
else:
    print(f"  {str(r)[:200]}")

# 7. Tools
print("\n[7] CUSTOM TOOLS")
r = api("GET", "/api/v1/tools/", token)
if isinstance(r, list):
    print(f"  Tools installed: {len(r)}")
    for t in r:
        name = t.get("name", t.get("id", "?"))
        desc = t.get("meta", {}).get("description", "")
        print(f"  - {name}: {desc}")
elif isinstance(r, dict):
    items = r.get("data", r.get("items", []))
    print(f"  Tools: {len(items)}")
    for t in items:
        print(f"  - {t.get('name', t.get('id', '?'))}")
else:
    print(f"  {str(r)[:200]}")

# 8. Web search
print("\n[8] WEB SEARCH CONFIG")
r = api("GET", "/api/v1/configs", token)
# Try getting web search config differently

# 9. Test Open Terminal health
print("\n[9] OPEN TERMINAL HEALTH")
try:
    # The terminal is accessible from open-webui container via Docker network
    req = urllib.request.Request("http://open-terminal:8000/health", headers={"Authorization": "Bearer a63a2a7ee2d5431d929c776122e3b706.hzHjrJlnfPd7cYfj"})
    resp = urllib.request.urlopen(req, timeout=5)
    print(f"  Status: {resp.read().decode()}")
except Exception as e:
    print(f"  Cannot reach from here (expected - different network): {e}")

# Try from host
try:
    req = urllib.request.Request("http://172.22.0.2:8000/health")
    resp = urllib.request.urlopen(req, timeout=5)
    print(f"  Via Docker IP: {resp.read().decode()}")
except Exception as e:
    print(f"  Via Docker IP failed: {e}")

print("\n" + "=" * 50)
print("AUDIT COMPLETE")
print("=" * 50)
