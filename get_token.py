import urllib.request, json
req = urllib.request.Request(
    "http://localhost:8080/api/v1/auths/signin",
    data=json.dumps({"email": "aaron@slothitude.com", "password": "Sloth2026!"}).encode(),
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req)
d = json.loads(resp.read().decode())
print(d["token"])
