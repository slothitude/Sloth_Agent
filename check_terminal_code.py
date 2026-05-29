import urllib.request, json, sys

# Get fresh token
signin = urllib.request.Request(
    "http://localhost:8080/api/v1/auths/signin",
    data=json.dumps({"email": "aaron@slothitude.com", "password": "Sloth2026!"}).encode(),
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(signin)
token = json.loads(resp.read().decode())["token"]

# Check all config keys for terminal
req = urllib.request.Request(
    "http://localhost:8080/api/v1/configs",
    headers={"Authorization": f"Bearer {token}"}
)
resp = urllib.request.urlopen(req)
configs = json.loads(resp.read().decode())

# Find terminal-related keys
for k, v in configs.items():
    if 'terminal' in k.lower() or 'terminal' in str(v).lower():
        print(f"{k}: {json.dumps(v, indent=2)}")

# Also print all keys
print("\n--- All config keys ---")
for k in sorted(configs.keys()):
    print(f"  {k}: {str(configs[k])[:100]}")
