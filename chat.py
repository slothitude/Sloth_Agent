"""Chat with Sloth Agent via OpenWebUI API."""
import urllib.request, json

BASE = "http://192.168.0.33:3000"

# Get token
req = urllib.request.Request(
    f"{BASE}/api/v1/auths/signin",
    data=json.dumps({"email": "aaron@slothitude.com", "password": "Sloth2026!"}).encode(),
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())["token"]

# Create a new chat
body = {
    "model": "sloth-agent",
    "messages": [{"role": "user", "content": "What OS are you running on? Run uname -a and tell me the result."}],
    "stream": False,
}

req = urllib.request.Request(
    f"{BASE}/api/chat/completions",
    data=json.dumps(body).encode(),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    method="POST"
)

try:
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read().decode())
    # Extract the response
    choices = result.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        print(f"Response:\n{content[:2000]}")
        if tool_calls:
            print(f"\nTool calls made: {len(tool_calls)}")
            for tc in tool_calls:
                print(f"  - {tc.get('function', {}).get('name')}: {tc.get('function', {}).get('arguments', '')[:200]}")
    else:
        print(f"Raw response: {json.dumps(result, indent=2)[:1000]}")
except urllib.error.HTTPError as e:
    print(f"Error {e.code}: {e.read().decode()[:500]}")
except Exception as e:
    print(f"Error: {e}")
