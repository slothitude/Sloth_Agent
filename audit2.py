"""Audit part 2: models, tools, terminal health."""
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

def api_raw(method, path, token):
    headers = {"Authorization": f"Bearer {token}"}
    req = urllib.request.Request(f"{BASE}{path}", headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

token = get_token()

# Models - try listing via GET with different endpoints
print("[5] MODELS")
code, body = api_raw("GET", "/api/v1/models/", token)
print(f"  /models/ -> {code}: {body[:300]}")

code, body = api_raw("GET", "/api/v1/models", token)
print(f"  /models -> {code}: {body[:300]}")

# Tools
print("\n[7] TOOLS")
code, body = api_raw("GET", "/api/v1/tools/", token)
print(f"  /tools/ -> {code}: {body[:500]}")

code, body = api_raw("GET", "/api/v1/tools", token)
print(f"  /tools -> {code}: {body[:500]}")

# Terminal health check from within Docker network
print("\n[9] TERMINAL HEALTH")
try:
    req = urllib.request.Request("http://open-terminal:8000/health")
    resp = urllib.request.urlopen(req, timeout=5)
    print(f"  open-terminal:8000 -> {resp.read().decode()}")
except Exception as e:
    print(f"  Failed: {e}")

try:
    req = urllib.request.Request("http://open-terminal:8000/api/v1/policies")
    resp = urllib.request.urlopen(req, timeout=5)
    print(f"  policies -> {resp.read().decode()[:200]}")
except Exception as e:
    print(f"  policies: {e}")

# Check LiteLLM reachable from container
print("\n[10] LITELLM CHECK")
try:
    req = urllib.request.Request(
        "http://192.168.0.33:4000/v1/models",
        headers={"Authorization": "Bearer sk-litellm-b15241627ba17201797f1446b25d82a9"}
    )
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read().decode())
    model_ids = [m["id"] for m in data.get("data", [])]
    print(f"  LiteLLM models: {len(model_ids)}")
    # Show local models
    local = [m for m in model_ids if not m.startswith("nim-") and not m.startswith("or-") and not m.startswith("zai-")]
    print(f"  Local/favorite: {local}")
except Exception as e:
    print(f"  Failed: {e}")

# Web search config
print("\n[11] WEB SEARCH")
code, body = api_raw("GET", "/api/v1/configs/websearch", token)
print(f"  websearch config -> {code}: {body[:300]}")
