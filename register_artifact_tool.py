"""Register artifacts tool as OpenWebUI custom tool."""
import json
import urllib.request
import sys

BASE = "http://192.168.0.33:3000"
EMAIL = "aaron@slothitude.com"
PASSWORD = "Sloth2026!"

# Get token
req = urllib.request.Request(
    f"{BASE}/api/v1/auths/signin",
    data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())["token"]

# Check if artifacts tool already exists
req = urllib.request.Request(
    f"{BASE}/api/v1/tools/",
    headers={"Authorization": f"Bearer {token}"},
)
resp = urllib.request.urlopen(req)
tools = json.loads(resp.read().decode())

# Delete old artifacts tool if exists
for t in tools:
    if t.get("name") == "artifacts" or t.get("id", "").startswith("artifacts"):
        del_req = urllib.request.Request(
            f"{BASE}/api/v1/tools/{t['id']}",
            headers={"Authorization": f"Bearer {token}"},
            method="DELETE",
        )
        urllib.request.urlopen(del_req)
        print(f"Deleted old tool: {t['id']}")

# Create artifacts tool
tool_body = {
    "id": "artifacts",
    "name": "artifacts",
    "meta": {
        "description": "Artifact tools — create, list, and update sandboxed code previews. Artifact server on port 8012 on Lappy."
    },
    "content": '''"""
title: Artifacts
description: Create, list, and update sandboxed code preview artifacts
required_open_webui_version: 0.3.0
version: 0.1.0
"""

import json
import urllib.request


class Tools:
    def __init__(self):
        self.base_url = "http://localhost:8012"

    def create_artifact(self, title: str, source: str, type: str = "html") -> str:
        """
        Create a sandboxed code artifact for preview.
        :param title: Display title for the artifact.
        :param source: The source code (HTML, SVG, React JSX, JavaScript, Mermaid, Python, CSS).
        :param type: Artifact type — one of: html, svg, react, javascript, mermaid, python, code, css.
        :return: JSON with artifact ID and preview URL.
        """
        body = json.dumps({"title": title, "source": source, "type": type}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/artifact",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        return json.dumps(data)

    def list_artifacts(self) -> str:
        """
        List all stored artifacts.
        :return: JSON list of artifacts with IDs, titles, types, and timestamps.
        """
        req = urllib.request.Request(f"{self.base_url}/artifacts")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        return json.dumps(data)

    def update_artifact(self, id: str, source: str) -> str:
        """
        Update the source code of an existing artifact.
        :param id: Artifact ID (from create_artifact or list_artifacts).
        :param source: New source code.
        :return: JSON confirmation.
        """
        body = json.dumps({"source": source}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/artifact/{id}/update",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        return json.dumps(data)
''',
    "access_control": None,
}

req = urllib.request.Request(
    f"{BASE}/api/v1/tools/create",
    data=json.dumps(tool_body).encode(),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
    method="POST",
)
try:
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read().decode())
    print(f"Artifacts tool registered: {result.get('id', 'ok')}")
except urllib.error.HTTPError as e:
    err = e.read().decode()
    print(f"Error: {e.code} {err}")
