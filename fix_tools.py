"""Enable custom tools on sloth-agent model and check tool status."""
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

# 1. Get sloth-agent model
models = api("GET", "/api/v1/models", token)
sloth = None
for m in models.get("data", []):
    if m["id"] == "sloth-agent":
        sloth = m
        break

if not sloth:
    print("ERROR: sloth-agent model not found")
    exit(1)

print(f"Found sloth-agent:")
print(f"  Current meta: {json.dumps(sloth.get('meta', {}), indent=2)[:500]}")
print(f"  Current params: {list(sloth.get('params', {}).keys())}")

# 2. Get all tool IDs
tools = api("GET", "/api/v1/tools/", token)
tool_ids = [t["id"] for t in tools]
print(f"\nAvailable tools: {tool_ids}")

# 3. Update sloth-agent to enable all tools
# In OpenWebUI, tools are enabled via the model's meta.tools array
meta = sloth.get("meta", {})
meta["tools"] = tool_ids  # Enable all custom tools

result = api("POST", "/api/v1/models/sloth-agent/update", token, {
    "name": sloth.get("name", "Sloth Agent"),
    "base_model_id": sloth.get("base_model_id", "zai-glm-5-turbo"),
    "meta": meta,
    "params": sloth.get("params", {}),
    "access_control": None,
})

if "error" not in result:
    print(f"\nSUCCESS - sloth-agent updated with tools:")
    print(f"  Tools enabled: {result.get('meta', {}).get('tools', [])}")
else:
    # Try alternate update endpoint
    print(f"\nUpdate failed: {result}")
    print("Trying PATCH...")
    result = api("PATCH", "/api/v1/models/sloth-agent", token, {
        "meta": meta,
    })
    print(f"PATCH result: {str(result)[:300]}")

print("\n=== Done ===")
