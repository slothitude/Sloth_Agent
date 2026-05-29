import urllib.request, json

TOKEN = open("/tmp/token.txt").read().strip()
req = urllib.request.Request(
    "http://localhost:8080/api/v1/terminals",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
try:
    resp = urllib.request.urlopen(req)
    print(resp.read().decode())
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode()[:500])
