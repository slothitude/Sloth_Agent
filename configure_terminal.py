"""Set terminal connection via /api/v1/configs/terminal_servers."""
import urllib.request, json

# Get fresh token
signin = urllib.request.Request(
    "http://localhost:8080/api/v1/auths/signin",
    data=json.dumps({"email": "aaron@slothitude.com", "password": "Sloth2026!"}).encode(),
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(signin)
token = json.loads(resp.read().decode())["token"]
print("Got token")

# First GET current terminal config
req = urllib.request.Request(
    "http://localhost:8080/api/v1/configs/terminal_servers",
    headers={"Authorization": f"Bearer {token}"}
)
resp = urllib.request.urlopen(req)
current = json.loads(resp.read().decode())
print(f"Current terminal config: {json.dumps(current, indent=2)}")

# Now POST the new config
terminal_config = {
    "TERMINAL_SERVER_CONNECTIONS": [
        {
            "id": "lappy",
            "name": "Lappy Terminal",
            "url": "http://open-terminal:8000",
            "enabled": True,
            "auth_type": "bearer",
            "key": "a63a2a7ee2d5431d929c776122e3b706.hzHjrJlnfPd7cYfj"
        }
    ]
}

req = urllib.request.Request(
    "http://localhost:8080/api/v1/configs/terminal_servers",
    data=json.dumps(terminal_config).encode(),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    method="POST"
)
try:
    resp = urllib.request.urlopen(req)
    body = json.loads(resp.read().decode())
    print(f"\nSUCCESS! Terminal config saved:")
    print(json.dumps(body, indent=2))
except urllib.error.HTTPError as e:
    err = e.read().decode()
    print(f"Error {e.code}: {err[:500]}")
