"""Fix memory tool and add git tool."""
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

# Delete old memory tool
api("DELETE", "/api/v1/tools/memory", token)

# Fixed Memory tool - uses /app/backend/data/ which is the persistent volume
tool_memory = '''"""
title: Memory
description: Save and recall information across conversations
author: slothitude
version: 0.1
required_open_webui_version: 0.3.0
"""
import json
import os

MEMORY_FILE = os.path.join(os.environ.get("DATA_DIR", "/app/backend/data"), "agent_memory.json")

class Tools:
    def __init__(self):
        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "w") as f:
                f.write("{}")

    def remember(self, key: str, value: str) -> str:
        """Save a key-value pair for later recall across conversations."""
        with open(MEMORY_FILE) as f:
            data = json.load(f)
        data[key] = value
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return "Remembered: " + key

    def recall(self, key: str) -> str:
        """Recall a previously saved value by key."""
        with open(MEMORY_FILE) as f:
            data = json.load(f)
        if key in data:
            return str(data[key])
        return "Nothing found for: " + key

    def list_memories(self) -> str:
        """List all saved memories."""
        with open(MEMORY_FILE) as f:
            data = json.load(f)
        if not data:
            return "No memories saved."
        lines = []
        for k, v in data.items():
            lines.append("- " + k + ": " + str(v)[:100])
        return "\\n".join(lines)
'''

# Tool 5: Git Operations
tool_git = '''"""
title: Git Tools
description: Git version control operations
author: slothitude
version: 0.1
required_open_webui_version: 0.3.0
"""
import subprocess

class Tools:
    def __init__(self):
        pass

    def git_status(self, path: str = "/home/user") -> str:
        """Show git status of a repository. Provide the repo path."""
        try:
            result = subprocess.run(
                ["git", "-C", path, "status", "--short"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout if result.stdout else "Clean working tree."
        except Exception as e:
            return "Error: " + str(e)

    def git_diff(self, path: str = "/home/user") -> str:
        """Show unstaged changes in a git repository."""
        try:
            result = subprocess.run(
                ["git", "-C", path, "diff"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout[:5000] if result.stdout else "No changes."
        except Exception as e:
            return "Error: " + str(e)

    def git_log(self, path: str = "/home/user", count: int = 10) -> str:
        """Show recent commit history. Args: path to repo, number of commits."""
        try:
            result = subprocess.run(
                ["git", "-C", path, "log", "-" + str(count), "--oneline"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout if result.stdout else "No commits."
        except Exception as e:
            return "Error: " + str(e)
'''

for tool_id, name, desc, content in [
    ("memory", "Memory", "Save/recall info across conversations", tool_memory),
    ("git_tools", "Git Tools", "Git status, diff, and log operations", tool_git),
]:
    result = api("POST", "/api/v1/tools/create", token, {
        "id": tool_id,
        "name": name,
        "content": content,
        "meta": {"description": desc},
        "access_control": None
    })
    status = "OK" if "error" not in result else str(result)[:150]
    print(f"  Tool '{name}': {status}")

print("\n=== All tools installed ===")
