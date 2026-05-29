"""Phase 4: Add custom tools to OpenWebUI."""
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
print("Token OK")

# Fix connections
result = api("GET", "/api/v1/configs/connections", token)
if isinstance(result, dict) and "error" not in result:
    result["ENABLE_DIRECT_CONNECTIONS"] = True
    result["ENABLE_BASE_MODELS_CACHE"] = result.get("ENABLE_BASE_MODELS_CACHE", True)
    result["OPENAI_API_BASE_URLS"] = ["http://192.168.0.33:4000/v1"]
    result["OPENAI_API_KEYS"] = ["sk-litellm-b15241627ba17201797f1446b25d82a9"]
    if "OPENAI_API_CONFIGS" not in result:
        result["OPENAI_API_CONFIGS"] = {}
    resp_result = api("POST", "/api/v1/configs/connections", token, result)
    print(f"Connections: {'ok' if 'error' not in resp_result else str(resp_result)[:200]}")

# Tool 1: Web Search
tool_search = '''"""
title: Web Search
description: Search the web using SearXNG
author: slothitude
version: 0.1
required_open_webui_version: 0.3.0
"""
import urllib.request
import urllib.parse
import json

class Tools:
    def __init__(self):
        pass

    def search_web(self, query: str) -> str:
        """Search the web for current information using SearXNG.
        Returns top 5 results with titles, URLs, and snippets.
        """
        url = "http://192.168.0.33:8888/search?q=" + urllib.parse.quote(query) + "&format=json&categories=general"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            results = data.get("results", [])[:5]
            output = []
            for r in results:
                title = r.get("title", "")
                link = r.get("url", "")
                content = r.get("content", "")
                output.append("- [" + title + "](" + link + ")\\n  " + content)
            return "\\n\\n".join(output) if output else "No results found."
        except Exception as e:
            return "Search error: " + str(e)
'''

# Tool 2: URL Fetcher
tool_fetch = '''"""
title: URL Fetcher
description: Fetch and extract text content from a URL
author: slothitude
version: 0.1
required_open_webui_version: 0.3.0
"""
import urllib.request
import re

class Tools:
    def __init__(self):
        pass

    def fetch_url(self, url: str) -> str:
        """Fetch a URL and return its text content.
        Good for reading documentation, APIs, articles.
        """
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            text = resp.read().decode("utf-8", errors="ignore")
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\\s+", " ", text).strip()
            return text[:10000]
        except Exception as e:
            return "Fetch error: " + str(e)
'''

# Tool 3: Memory
tool_memory = '''"""
title: Memory
description: Save and recall information across conversations
author: slothitude
version: 0.1
required_open_webui_version: 0.3.0
"""
import json
from pathlib import Path

MEMORY_FILE = Path("/home/user/.agent_memory.json")

class Tools:
    def __init__(self):
        if not MEMORY_FILE.exists():
            MEMORY_FILE.write_text("{}")

    def remember(self, key: str, value: str) -> str:
        """Save a key-value pair for later recall across conversations."""
        data = json.loads(MEMORY_FILE.read_text())
        data[key] = value
        MEMORY_FILE.write_text(json.dumps(data, indent=2))
        return "Remembered: " + key

    def recall(self, key: str) -> str:
        """Recall a previously saved value by key."""
        data = json.loads(MEMORY_FILE.read_text())
        if key in data:
            return str(data[key])
        return "Nothing found for: " + key

    def list_memories(self) -> str:
        """List all saved memories."""
        data = json.loads(MEMORY_FILE.read_text())
        if not data:
            return "No memories saved."
        lines = []
        for k, v in data.items():
            lines.append("- " + k + ": " + str(v)[:100])
        return "\\n".join(lines)
'''

# Tool 4: Docker Manager
tool_docker = '''"""
title: Docker Manager
description: Manage Docker containers
author: slothitude
version: 0.1
required_open_webui_version: 0.3.0
"""
import subprocess

class Tools:
    def __init__(self):
        pass

    def docker_ps(self) -> str:
        """List running Docker containers with their status and ports."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout[:3000] if result.stdout else "No containers."
        except Exception as e:
            return "Error: " + str(e)

    def docker_logs(self, container: str, lines: int = 50) -> str:
        """Get container logs. Args: container name, number of lines."""
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(lines), container],
                capture_output=True, text=True, timeout=10
            )
            output = (result.stdout + result.stderr)[-3000:]
            return output if output else "No logs."
        except Exception as e:
            return "Error: " + str(e)

    def docker_restart(self, container: str) -> str:
        """Restart a Docker container by name."""
        try:
            result = subprocess.run(
                ["docker", "restart", container],
                capture_output=True, text=True, timeout=30
            )
            return "Restarted " + container + ": " + result.stdout.strip()
        except Exception as e:
            return "Error: " + str(e)
'''

tools = [
    ("web_search", "Web Search", "Search the web via SearXNG", tool_search),
    ("url_fetcher", "URL Fetcher", "Fetch and extract text from URLs", tool_fetch),
    ("memory", "Memory", "Save and recall info across conversations", tool_memory),
    ("docker_manager", "Docker Manager", "Manage Docker containers", tool_docker),
]

for tool_id, name, desc, content in tools:
    result = api("POST", "/api/v1/tools/create", token, {
        "id": tool_id,
        "name": name,
        "content": content,
        "meta": {"description": desc},
        "access_control": None
    })
    status = "OK" if "error" not in result else str(result)[:150]
    print(f"  Tool '{name}': {status}")

print("\n=== Phase 4 complete ===")
