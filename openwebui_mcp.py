"""OpenWebUI MCP Server — control OpenWebUI chats, models, and tools from Claude Code.

Tools:
  openweb_chat       — Send a message to sloth-agent and wait for response
  openweb_read       — Read chat history
  openweb_list_chats — List all chats
  openweb_models     — List available models
  openweb_delete_chat— Delete a chat
"""
import json
import os
import re
import sys
import time
import uuid
import urllib.parse
import urllib.request
import urllib.error

import jinja2

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE = "http://192.168.0.33:3000"
MODEL = "sloth-agent"
EMAIL = "aaron@slothitude.com"
PASSWORD = "Sloth2026!"
POLL_INTERVAL = 3
MAX_POLL = 300

# Alphabetty config
ALPHABETTY_BASE = "http://100.84.161.63:7700"
ALPHABETTY_BOOTSTRAP = "alphabetty-bootstrap-secret"
_alphabetty_key = None

# Artifact server config
ARTIFACT_BASE = "http://192.168.0.33:8012"

# Jinja2 template engine
HERE = os.path.dirname(os.path.abspath(__file__))
VAULT_ROOT = os.path.join(HERE, "vault")
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(HERE, "templates")),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
# Skills Jinja2 env — loads from vault/skills/
_skills_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(HERE, "vault", "skills")),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
# Agents Jinja2 env — loads from vault/agents/
_agents_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(HERE, "vault", "agents")),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
_current_user = "aaron"  # default user for vault logging

# Allowed paths for file_system tools (whitelist roots)
FILE_SYSTEM_ROOTS = [
    os.path.join(HERE, "vault"),
    os.path.join(HERE),
    "C:/Users/aaron/Desktop/dev",
    "C:/Users/aaron/Desktop/tomb",
    "C:/Users/aaron/Desktop",
    "C:/Users/aaron/Desktop/hotswap",
    "/tmp",
]

# Multi-user auth cache: email -> token
_user_tokens = {}


def get_token_for(email=None, password=None):
    """Get auth token for a specific user, cached."""
    if email is None:
        email = EMAIL
        password = PASSWORD
    if email in _user_tokens:
        return _user_tokens[email]
    req = urllib.request.Request(
        f"{BASE}/api/v1/auths/signin",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    token = json.loads(resp.read().decode())["token"]
    _user_tokens[email] = token
    return token


def get_token():
    req = urllib.request.Request(
        f"{BASE}/api/v1/auths/signin",
        data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())["token"]


def api(method, path, token, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:500]
        return {"error": f"HTTP {e.code}: {err}"}
    except Exception as e:
        return {"error": str(e)}


def strip_reasoning(text):
    return re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL).strip()


# --- Tool implementations ---

def execute_search_web(query):
    """Execute a SearXNG search and return formatted results."""
    url = f"http://192.168.0.33:8888/search?q={urllib.parse.quote(query)}&format=json"
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        results = []
        for r in data.get("results", [])[:5]:
            results.append(f"- **{r.get('title','')}**\n  URL: {r.get('url','')}\n  {r.get('content','')}")
        return "\n\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {e}"


def execute_fetch_url(url):
    """Fetch a URL and return extracted text content."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
        # Strip HTML tags for plain text
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000] if text else "Empty page."
    except Exception as e:
        return f"Fetch error: {e}"


def execute_get_current_timestamp():
    """Return current UTC timestamp."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# --- Alphabetty integration ---

def get_alphabetty_key():
    global _alphabetty_key
    if _alphabetty_key:
        return _alphabetty_key
    try:
        req = urllib.request.Request(
            f"{ALPHABETTY_BASE}/api/auth/session/acquire",
            data=json.dumps({"name": "openwebui-mcp"}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Bootstrap-Token": ALPHABETTY_BOOTSTRAP,
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        _alphabetty_key = data["api_key"]
        return _alphabetty_key
    except Exception as e:
        return None


def alphabetty_request(method, path, body=None, params=None, timeout=120):
    key = get_alphabetty_key()
    if not key:
        return {"error": "Alphabetty auth failed"}
    url = f"{ALPHABETTY_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode("utf-8"))


def alphabetty_sse_post(path, body):
    """POST to Alphabetty SSE endpoint, consume stream, return aggregated result."""
    key = get_alphabetty_key()
    if not key:
        return "Alphabetty auth failed"
    req = urllib.request.Request(
        f"{ALPHABETTY_BASE}{path}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=300)
    tokens = []
    for raw_line in resp:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        etype = event.get("type")
        if etype == "token":
            tokens.append(event.get("content", ""))
        elif etype == "done":
            break
        elif etype == "error":
            return event.get("error", "Unknown error")
    return "".join(tokens) if tokens else json.dumps({"status": "completed"})


def execute_deep_research(query, depth=3, mode="detailed"):
    return alphabetty_sse_post("/api/research", {"query": query, "depth": depth, "mode": mode})


def execute_search_and_read(query, max_results=3):
    try:
        result = alphabetty_request("POST", "/api/search-and-read", {
            "query": query, "max_results": max_results,
        })
        return json.dumps(result) if isinstance(result, dict) else str(result)
    except Exception as e:
        return f"Search-and-read error: {e}"


def execute_ask_ai(query, mode="concise"):
    return alphabetty_sse_post("/api/chat", {"query": query, "mode": mode, "search_enabled": True})


def execute_bash(command, host="local"):
    """Execute a bash command locally or via SSH to Lappy."""
    import subprocess
    # Blocklist dangerous commands
    cmd_lower = command.lower().strip()
    blocked_patterns = [
        "rm -rf /", "rm -rf /*", "mkfs", "format ", ":(){ :|:& };:",
        "dd if=", "chmod -r 777 /", "> /dev/sd", "shutdown", "reboot",
        "init 0", "init 6", "halt", "poweroff", "wipe", "shred",
    ]
    for pat in blocked_patterns:
        if pat in cmd_lower:
            return f"Error: Command blocked for safety (matched '{pat}')"
    timeout = 60
    try:
        if host == "lappy":
            proc = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 "aaron@192.168.0.33", command],
                capture_output=True, text=True, timeout=timeout,
            )
        else:
            proc = subprocess.run(
                ["bash", "-c", command],
                capture_output=True, text=True, timeout=timeout,
            )
        output = ""
        if proc.stdout:
            output += proc.stdout[:5000]
        if proc.stderr:
            output += f"\nSTDERR:\n{proc.stderr[:2000]}"
        if proc.returncode != 0:
            output += f"\nExit code: {proc.returncode}"
        return output.strip() if output.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return "Error: bash not found"
    except Exception as e:
        return f"Error: {e}"


def _fs_safe(path):
    """Check if a path is within allowed file system roots."""
    p = os.path.normpath(path.replace("\\", "/"))
    for root in FILE_SYSTEM_ROOTS:
        if os.path.normpath(root).startswith(os.path.normpath(p)):
            return True, p
        if p.startswith(os.path.normpath(root)):
            return True, p
    return False, p


def execute_read_file(path):
    """Read a file and return its contents."""
    try:
        safe, p = _fs_safe(path)
        if not safe:
            return f"Error: Path '{path}' is outside allowed directories."
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return content[:10000] if content else "(empty file)"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except IsADirectoryError:
        return f"Error: Path is a directory: {path}"
    except Exception as e:
        return f"Error: {e}"


def execute_write_file(path, content):
    """Write content to a file."""
    try:
        safe, p = _fs_safe(path)
        if not safe:
            return f"Error: Path '{path}' is outside allowed directories."
        import os
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Error: {e}"


def execute_edit_file(path, old_text, new_text):
    """Edit a file by replacing old_text with new_text."""
    try:
        safe, p = _fs_safe(path)
        if not safe:
            return f"Error: Path '{path}' is outside allowed directories."
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        if old_text not in content:
            return f"Error: old_text not found in {path}"
        count = content.count(old_text)
        content = content.replace(old_text, new_text)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Replaced {count} occurrence(s) in {path}"
    except Exception as e:
        return f"Error: {e}"


def execute_list_directory(path):
    """List directory contents."""
    try:
        p = path.replace("\\", "/")
        import os
        entries = []
        for entry in sorted(os.listdir(p)):
            full = os.path.join(p, entry)
            if os.path.isdir(full):
                entries.append(f"  {entry}/")
            else:
                size = os.path.getsize(full)
                entries.append(f"  {entry} ({size} bytes)")
        return "\n".join(entries) if entries else "(empty directory)"
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except Exception as e:
        return f"Error: {e}"


def _cdp_request(path, method="GET", body=None):
    """Make a request to Alphabetty CDP API."""
    key = get_alphabetty_key()
    if not key:
        return "Alphabetty auth failed"
    url = f"{ALPHABETTY_BASE}{path}"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode("utf-8"))


def execute_browse_page(url):
    """Navigate to URL and get page content via Alphabetty CDP."""
    try:
        _cdp_request("/api/cdp/navigate", "POST", {"url": url})
        result = _cdp_request("/api/cdp/content")
        content = result.get("content", "")
        return content[:8000] if content else "(empty page)"
    except Exception as e:
        return f"Browse error: {e}"


def execute_screenshot():
    """Take a screenshot via Alphabetty CDP."""
    try:
        result = _cdp_request("/api/cdp/screenshot", "POST", {"format": "jpeg"})
        return json.dumps({"status": "screenshot taken", "size": result.get("size", 0)})
    except Exception as e:
        return f"Screenshot error: {e}"


def execute_click_element(selector):
    """Click element via Alphabetty CDP."""
    try:
        result = _cdp_request("/api/cdp/click", "POST", {"selector": selector})
        return json.dumps(result)[:500]
    except Exception as e:
        return f"Click error: {e}"


def execute_type_text(selector, text):
    """Type text via Alphabetty CDP."""
    try:
        result = _cdp_request("/api/cdp/type", "POST", {"selector": selector, "text": text})
        return json.dumps(result)[:500]
    except Exception as e:
        return f"Type error: {e}"


def execute_extract_data(expression):
    """Extract data via JavaScript."""
    try:
        result = _cdp_request("/api/cdp/extract", "POST", {"expression": expression})
        return json.dumps(result)[:3000]
    except Exception as e:
        return f"Extract error: {e}"


def execute_analyze_image(image_source, prompt):
    """Analyze image via Alphabetty's image analysis."""
    try:
        if image_source.startswith("http"):
            result = alphabetty_request("POST", "/api/files/analyze", {
                "url": image_source, "query": prompt,
            })
        else:
            result = alphabetty_request("POST", "/api/files/analyze", {
                "file_path": image_source, "query": prompt,
            })
        return json.dumps(result)[:5000] if isinstance(result, dict) else str(result)[:5000]
    except Exception as e:
        return f"Image analysis error: {e}"


def execute_generate_image(prompt, width=1024, height=1024):
    """Generate image via Alphabetty's ComfyUI."""
    try:
        result = alphabetty_request("POST", "/api/images/generate", {
            "prompt": prompt, "width": width, "height": height,
        }, timeout=120)
        return json.dumps(result)[:2000] if isinstance(result, dict) else str(result)[:2000]
    except Exception as e:
        return f"Image generation error: {e}"


def execute_graph_search(query, limit=10):
    """Search the Alphabetty knowledge graph."""
    try:
        result = alphabetty_request("GET", f"/api/graph/search?query={urllib.parse.quote(query)}&limit={limit}")
        return json.dumps(result)[:5000] if isinstance(result, (dict, list)) else str(result)[:5000]
    except Exception as e:
        return f"Graph search error: {e}"


def execute_graph_stats():
    """Get knowledge graph statistics."""
    try:
        result = alphabetty_request("GET", "/api/graph/stats")
        return json.dumps(result)[:3000] if isinstance(result, dict) else str(result)[:3000]
    except Exception as e:
        return f"Graph stats error: {e}"


def execute_entity_graph(entity_name, depth=2):
    """Get entity with neighbors from the knowledge graph."""
    try:
        result = alphabetty_request("GET", f"/api/graph/entity/{urllib.parse.quote(entity_name)}?depth={depth}")
        return json.dumps(result)[:5000] if isinstance(result, dict) else str(result)[:5000]
    except Exception as e:
        return f"Entity graph error: {e}"


def execute_list_tags():
    """List all tags in the knowledge graph."""
    try:
        result = alphabetty_request("GET", "/api/graph/tags")
        return json.dumps(result)[:3000] if isinstance(result, (dict, list)) else str(result)[:3000]
    except Exception as e:
        return f"List tags error: {e}"


def execute_list_spaces():
    """List all spaces."""
    try:
        result = alphabetty_request("GET", "/api/spaces")
        return json.dumps(result)[:3000] if isinstance(result, (dict, list)) else str(result)[:3000]
    except Exception as e:
        return f"List spaces error: {e}"


def execute_list_conversations():
    """List all conversations."""
    try:
        result = alphabetty_request("GET", "/api/conversations")
        return json.dumps(result)[:5000] if isinstance(result, (dict, list)) else str(result)[:5000]
    except Exception as e:
        return f"List conversations error: {e}"


# --- Obsidian vault ---


def _vault_safe(path):
    full = os.path.normpath(os.path.join(VAULT_ROOT, path.lstrip("/")))
    if not full.startswith(os.path.normpath(VAULT_ROOT)):
        return None
    return full


# --- Alphabetty: Workflow tools ---


def execute_workflow_create(name, nodes="[]", connections="{}", active=False):
    return alphabetty_request("POST", "/api/workflows", {
        "name": name, "nodes": json.loads(nodes), "connections": json.loads(connections), "active": active,
    })


def execute_workflow_list():
    return alphabetty_request("GET", "/api/workflows")


def execute_workflow_run(workflow_id, data="{}"):
    return alphabetty_request("POST", f"/api/workflows/{workflow_id}/run", json.loads(data))


def execute_workflow_status(workflow_id, limit=10):
    return alphabetty_request("GET", f"/api/workflows/{workflow_id}/status?limit={limit}")


def execute_workflow_delete(workflow_id):
    return alphabetty_request("DELETE", f"/api/workflows/{workflow_id}")


# --- Alphabetty: Sign-in tools ---


def execute_signin_start(url, username, password):
    return alphabetty_request("POST", "/api/signin/start", {
        "url": url, "username": username, "password": password,
    })


def execute_signin_auto(name):
    return alphabetty_request("POST", "/api/signin/auto", {"name": name})


def execute_signin_status():
    return alphabetty_request("GET", "/api/signin/status")


def execute_signin_submit_2fa(code):
    return alphabetty_request("POST", "/api/signin/submit_2fa", {"code": code})


def execute_signin_check_2fa():
    return alphabetty_request("GET", "/api/signin/check_2fa")


def execute_signin_save(name, url, username, password, totp_secret="", selectors=""):
    body = {"name": name, "url": url, "username": username, "password": password}
    if totp_secret:
        body["totp_secret"] = totp_secret
    if selectors:
        body["selectors"] = selectors
    return alphabetty_request("POST", "/api/signin/save", body)


# --- Alphabetty: Macro tools ---


def execute_macro_record_start(name, url=""):
    return alphabetty_request("POST", "/api/macros/record/start", {"name": name, "url": url})


def execute_macro_record_stop():
    return alphabetty_request("POST", "/api/macros/record/stop")


def execute_macro_record_browser(name, url=""):
    return alphabetty_request("POST", "/api/macros/record/browser", {"name": name, "url": url})


def execute_macro_record_stop_browser():
    return alphabetty_request("POST", "/api/macros/record/stop/browser")


def execute_macro_play(macro_id):
    return alphabetty_request("POST", "/api/macros/play", {"macro_id": macro_id})


def execute_macro_list():
    return alphabetty_request("GET", "/api/macros")


# --- Alphabetty: Video/YouTube tools ---


def execute_play_video(url):
    return alphabetty_request("POST", "/api/play/video", {"url": url})


def execute_youtube_play(query):
    return alphabetty_request("POST", "/api/youtube/play", {"query": query})


# --- Alphabetty: Other tools ---


def execute_read_url(url, max_length=50000, format="markdown"):
    return alphabetty_request("POST", "/api/read-url", {
        "url": url, "max_length": max_length, "format": format,
    })


def execute_upload_file(file_path, query=""):
    """Upload a file from local path to Alphabetty for analysis."""
    import base64 as b64
    p = file_path.replace("\\", "/")
    if not os.path.isfile(p):
        return f"Error: File not found: {file_path}"
    with open(p, "rb") as f:
        data = b64.b64encode(f.read()).decode()
    body = {"filename": os.path.basename(p), "data": data}
    if query:
        body["query"] = query
    return alphabetty_request("POST", "/api/files/upload", body, timeout=30)


def execute_download_save(url, filename="", subdir=""):
    return alphabetty_request("POST", "/api/downloads/save", {
        "url": url, "filename": filename, "subdir": subdir,
    })


def execute_download_list(subdir=""):
    path = f"/api/downloads/list"
    if subdir:
        path += f"?subdir={subdir}"
    return alphabetty_request("GET", path)


def execute_vault_list(path=""):
    target = _vault_safe(path)
    if not target or not os.path.isdir(target):
        return f"Error: Invalid path: {path}"
    entries = []
    for entry in sorted(os.listdir(target)):
        if entry == ".obsidian":
            continue
        full = os.path.join(target, entry)
        if os.path.isdir(full):
            entries.append(f"  {entry}/")
        else:
            entries.append(f"  {entry} ({os.path.getsize(full)} bytes)")
    return "\n".join(entries) if entries else "(empty)"


def execute_vault_read(path):
    target = _vault_safe(path)
    if not target:
        return "Error: Path outside vault"
    if not os.path.isfile(target):
        return f"Error: Not found: {path}"
    with open(target, "r", encoding="utf-8", errors="replace") as f:
        return f.read()[:10000] or "(empty)"


def execute_vault_write(path, content):
    target = _vault_safe(path)
    if not target:
        return "Error: Path outside vault"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if not content.strip().startswith("---"):
        ts = time.strftime("%Y-%m-%d")
        content = f"---\ncreated: {ts}\ntags: []\n---\n\n{content}"
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Written {len(content)} chars to {path}"


def execute_speech_to_text(audio_base64, language=None):
    """Send base64 audio to STT server (faster-whisper) and return transcription."""
    import base64 as b64
    try:
        body = json.dumps({"audio": audio_base64, "language": language}).encode()
        req = urllib.request.Request(
            f"http://192.168.0.33:8007/v1/audio/transcriptions/json",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        return data.get("text", ""), data.get("language", ""), data.get("duration", 0)
    except Exception as e:
        return f"STT error: {e}"


def execute_text_to_speech(text, voice="af_bella", speed=1.0):
    """Send text to TTS server (kokoro-onnx) and return base64 WAV audio."""
    try:
        body = json.dumps({"text": text, "voice": voice, "speed": speed}).encode()
        req = urllib.request.Request(
            f"http://192.168.0.33:8006/tts",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=60)
        wav_bytes = resp.read()
        import base64 as b64
        audio_b64 = b64.b64encode(wav_bytes).decode()
        gen_time = resp.headers.get("X-Gen-Time", "?")
        audio_dur = resp.headers.get("X-Audio-Duration", "?")
        return {
            "audio_base64": audio_b64[:100] + "...",
            "audio_size_bytes": len(wav_bytes),
            "gen_time": gen_time,
            "audio_duration": audio_dur,
            "status": "ok",
        }
    except Exception as e:
        return f"TTS error: {e}"


def execute_create_artifact(title, source, atype="html"):
    """Create a sandboxed code artifact."""
    try:
        body = json.dumps({"title": title, "source": source, "type": atype}).encode()
        req = urllib.request.Request(
            f"{ARTIFACT_BASE}/artifact",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def execute_list_artifacts():
    """List all stored artifacts."""
    try:
        req = urllib.request.Request(f"{ARTIFACT_BASE}/artifacts")
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def execute_update_artifact(aid, source):
    """Update source code of an existing artifact."""
    try:
        body = json.dumps({"source": source}).encode()
        req = urllib.request.Request(
            f"{ARTIFACT_BASE}/artifact/{aid}/update",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def execute_vault_search(query, max_results=10):
    results = []
    ql = query.lower()
    for root, dirs, files in os.walk(os.path.normpath(VAULT_ROOT)):
        dirs[:] = [d for d in dirs if d != ".obsidian"]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, VAULT_ROOT).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                if ql in text.lower():
                    idx = text.lower().index(ql)
                    ctx = text[max(0, idx-60):idx+len(ql)+60].replace("\n", " ").strip()
                    results.append(f"- **{rel}**\n  ...{ctx}...")
                    if len(results) >= max_results:
                        break
            except Exception:
                continue
        if len(results) >= max_results:
            break
    if not results:
        return f"No notes matching '{query}'."
    return f"Found {len(results)}:\n\n" + "\n\n".join(results)


# --- Skills system ---


def _parse_skill_frontmatter(text):
    """Parse YAML frontmatter from a skill file. Returns (metadata_dict, body_str)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end < 0:
        return {}, text
    yaml_str = text[3:end].strip()
    body = text[end + 3:].strip()
    meta = {}
    for line in yaml_str.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("\"'")
    return meta, body


def execute_skill_list():
    """List all available skills from vault/skills/."""
    skills_dir = os.path.join(HERE, "vault", "skills")
    if not os.path.isdir(skills_dir):
        return "No skills directory found."
    entries = []
    for fname in sorted(os.listdir(skills_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(skills_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
            meta, _ = _parse_skill_frontmatter(text)
            name = meta.get("name", fname[:-3])
            desc = meta.get("description", "(no description)")
            cat = meta.get("category", "")
            entries.append(f"- **{fname[:-3]}** — {desc}" + (f" [{cat}]" if cat else ""))
        except Exception:
            entries.append(f"- **{fname[:-3]}** — (error reading)")
    if not entries:
        return "No skills found. Add .md files to vault/skills/"
    return f"Available skills ({len(entries)}):\n\n" + "\n".join(entries)


def execute_skill_load(name):
    """Load a skill template by name (without .md extension)."""
    skills_dir = os.path.join(HERE, "vault", "skills")
    fname = name if name.endswith(".md") else f"{name}.md"
    fpath = os.path.join(skills_dir, fname)
    if not os.path.isfile(fpath):
        return f"Error: Skill '{name}' not found. Use skill_list to see available skills."
    with open(fpath, "r", encoding="utf-8") as f:
        text = f.read()
    meta, body = _parse_skill_frontmatter(text)
    result = f"## Skill: {meta.get('name', name)}\n"
    if meta.get("description"):
        result += f"**Description**: {meta['description']}\n"
    if meta.get("category"):
        result += f"**Category**: {meta['category']}\n"
    result += f"\n---\n\n{body}"
    return result


def execute_skill_execute(name, variables=None):
    """Load and render a skill template with variables, return the prompt."""
    skills_dir = os.path.join(HERE, "vault", "skills")
    fname = name if name.endswith(".md") else f"{name}.md"
    fpath = os.path.join(skills_dir, fname)
    if not os.path.isfile(fpath):
        return f"Error: Skill '{name}' not found. Use skill_list to see available skills."
    with open(fpath, "r", encoding="utf-8") as f:
        text = f.read()
    meta, body = _parse_skill_frontmatter(text)
    # Parse variables from JSON string or key=value pairs
    if variables:
        if isinstance(variables, str):
            try:
                var_dict = json.loads(variables)
            except json.JSONDecodeError:
                # Try key=value pairs
                var_dict = {}
                for pair in variables.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        var_dict[k.strip()] = v.strip()
                else:
                    var_dict = {}
        else:
            var_dict = variables
    else:
        var_dict = {}
    # Render template
    try:
        template = _skills_env.from_string(body)
        rendered = template.render(**var_dict)
    except jinja2.TemplateError as e:
        return f"Error rendering skill '{name}': {e}"
    skill_name = meta.get("name", name)
    result = {
        "skill": skill_name,
        "category": meta.get("category", ""),
        "prompt": rendered,
    }
    return result


# --- Agents system ---


def _get_agent_summaries():
    """Scan vault/agents/ and return list of (slug, name, description, tools, model)."""
    agents_dir = os.path.join(HERE, "vault", "agents")
    summaries = []
    if not os.path.isdir(agents_dir):
        return summaries
    for fname in sorted(os.listdir(agents_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(agents_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
            meta, _ = _parse_skill_frontmatter(text)
            slug = fname[:-3]
            summaries.append({
                "slug": slug,
                "name": meta.get("name", slug),
                "description": meta.get("description", ""),
                "tools": [t.strip() for t in meta.get("tools", "").split(",") if t.strip()],
                "model": meta.get("model", ""),
            })
        except Exception:
            continue
    return summaries


def execute_agent_list():
    """List all available agents from vault/agents/."""
    summaries = _get_agent_summaries()
    if not summaries:
        return "No agents found. Add .md files to vault/agents/ with YAML frontmatter."
    entries = []
    for a in summaries:
        tools_str = ", ".join(a["tools"]) if a["tools"] else "(no tools)"
        model_str = f" [{a['model']}]" if a["model"] else ""
        entries.append(f"- **{a['slug']}** — {a['description']}{model_str}\n  Tools: {tools_str}")
    return f"Available agents ({len(summaries)}):\n\n" + "\n\n".join(entries)


def execute_agent_load(name):
    """Load an agent template by name (without .md extension). Returns full template."""
    agents_dir = os.path.join(HERE, "vault", "agents")
    fname = name if name.endswith(".md") else f"{name}.md"
    fpath = os.path.join(agents_dir, fname)
    if not os.path.isfile(fpath):
        return f"Error: Agent '{name}' not found. Use agent_list to see available agents."
    with open(fpath, "r", encoding="utf-8") as f:
        text = f.read()
    meta, body = _parse_skill_frontmatter(text)
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    result = f"## Agent: {meta.get('name', name)}\n"
    result += f"**Description**: {meta.get('description', '')}\n"
    result += f"**Tools**: {', '.join(tools) if tools else '(none)'}\n"
    if meta.get("model"):
        result += f"**Model**: {meta['model']}\n"
    result += f"\n---\n\n{body}"
    return result


def execute_agent_execute(name, task):
    """Load an agent template, render system prompt, and delegate the task."""
    agents_dir = os.path.join(HERE, "vault", "agents")
    fname = name if name.endswith(".md") else f"{name}.md"
    fpath = os.path.join(agents_dir, fname)
    if not os.path.isfile(fpath):
        return f"Error: Agent '{name}' not found. Use agent_list to see available agents."
    with open(fpath, "r", encoding="utf-8") as f:
        text = f.read()
    meta, body = _parse_skill_frontmatter(text)
    # Parse tools
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    model_override = meta.get("model", "")
    # Render Jinja2 system prompt
    try:
        template = _agents_env.from_string(body)
        rendered = template.render(
            task=task,
            agent_name=meta.get("name", name),
            date=time.strftime("%Y-%m-%d"),
        )
    except jinja2.TemplateError as e:
        return f"Error rendering agent '{name}': {e}"
    # Delegate with template config
    return execute_delegate_to(
        agent_id=name,
        message=task,
        system_prompt=rendered,
        allowed_tools=tools,
        model_override=model_override,
    )


def execute_agent_create(name, description, tools, system_prompt, model=""):
    """Create a new agent template in vault/agents/."""
    agents_dir = os.path.join(HERE, "vault", "agents")
    os.makedirs(agents_dir, exist_ok=True)
    slug = re.sub(r"[^\w\s-]", "", name.lower()).replace(" ", "-").strip("-")[:50]
    if not slug:
        slug = "unnamed"
    fpath = os.path.join(agents_dir, f"{slug}.md")
    if os.path.isfile(fpath):
        return f"Error: Agent '{slug}' already exists at vault/agents/{slug}.md. Delete it first or use a different name."

    # Build frontmatter
    fm_lines = ["---"]
    fm_lines.append(f"name: {name}")
    fm_lines.append(f"description: {description}")
    fm_lines.append(f"tools: {tools}")
    if model:
        fm_lines.append(f"model: {model}")
    fm_lines.append("---")
    frontmatter = "\n".join(fm_lines)

    content = f"{frontmatter}\n\n{system_prompt}"
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)

    # Rebuild dynamic MCP tools so the new agent is immediately available
    new_tools = _build_agent_mcp_tools()
    TOOLS.update(new_tools)

    return f"Agent '{slug}' created at vault/agents/{slug}.md with tools: {tools}. Now available as openweb_agent_{slug} MCP tool."


def execute_agent_delete(name):
    """Delete an agent template from vault/agents/."""
    agents_dir = os.path.join(HERE, "vault", "agents")
    fname = name if name.endswith(".md") else f"{name}.md"
    fpath = os.path.join(agents_dir, fname)
    if not os.path.isfile(fpath):
        return f"Error: Agent '{name}' not found."
    os.remove(fpath)
    return f"Agent '{name}' deleted."


# --- Extended Thinking ---


def execute_thinking_log(title, reasoning, conclusion=""):
    """Save a reasoning trace to vault/thinking/ for transparency."""
    thinking_dir = os.path.join(VAULT_ROOT, "thinking")
    os.makedirs(thinking_dir, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    date = time.strftime("%Y-%m-%d")
    slug = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-").strip("-")[:50] or "trace"
    fname = f"{date}-{slug}.md"
    fpath = os.path.join(thinking_dir, fname)
    counter = 1
    while os.path.exists(fpath):
        fpath = os.path.join(thinking_dir, f"{date}-{slug}-{counter}.md")
        counter += 1
    note = f"---\ncreated: {ts}\ntags: [thinking, reasoning]\ntitle: {title}\n---\n\n# {title}\n\n{reasoning}\n"
    if conclusion:
        note += f"\n## Conclusion\n{conclusion}\n"
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(note)
    return f"Thinking trace saved to vault/thinking/{os.path.basename(fpath)}"


# --- Chat logging to vault ---


# Tool subsets per sub-agent
AGENT_TOOLS = {
    "researcher": ["search_and_read", "browse_page", "extract_data", "get_current_timestamp"],
    "coder": ["execute_bash", "read_file", "write_file", "edit_file", "list_directory"],
    "writer": ["search_and_read", "browse_page", "get_current_timestamp"],
}


def execute_delegate_to(agent_id, message, system_prompt=None, allowed_tools=None, model_override=None):
    """Delegate a task to a sub-agent with its own tools and streaming tool loop.

    Resolution order: provided params > template file > AGENT_TOOLS dict.
    """
    # If no explicit config, try loading from template file
    if allowed_tools is None and system_prompt is None:
        agents_dir = os.path.join(HERE, "vault", "agents")
        fname = agent_id if agent_id.endswith(".md") else f"{agent_id}.md"
        fpath = os.path.join(agents_dir, fname)
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read()
            meta, body = _parse_skill_frontmatter(text)
            allowed_tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
            model_override = meta.get("model", "")
            if body.strip():
                try:
                    tpl = _agents_env.from_string(body)
                    system_prompt = tpl.render(
                        task=message,
                        agent_name=meta.get("name", agent_id),
                        date=time.strftime("%Y-%m-%d"),
                    )
                except jinja2.TemplateError:
                    system_prompt = body

    # Fallback to hardcoded AGENT_TOOLS
    if allowed_tools is None:
        allowed_tools = AGENT_TOOLS.get(agent_id, [])
    if not allowed_tools:
        return f"Error: No tools defined for agent '{agent_id}'. Create a template in vault/agents/{agent_id}.md or add to AGENT_TOOLS."

    # Filter CUSTOM_TOOL_SCHEMAS to only include allowed tools
    agent_schemas = [t for t in CUSTOM_TOOL_SCHEMAS
                     if t["function"]["name"] in allowed_tools]

    try:
        body = {
            "chat_id": "",
            "id": str(uuid.uuid4()),
            "session_id": str(uuid.uuid4()),
            "messages": [{"role": "user", "content": message}],
            "model": model_override or agent_id if agent_id in AGENT_TOOLS else MODEL,
            "stream": True,
            "system": system_prompt or f"You are a {agent_id} sub-agent. Complete the task.",
            "tools": agent_schemas,
            "tool_ids": ["alphabetty", "bash_tool", "file_system", "browser_control", "vision", "knowledge_graph", "graph_visuals", "obsidian", "voice", "artifacts", "skills"],
            "features": {"web_search": False},
        }

        max_loops = 10
        all_content = ""

        for loop in range(max_loops):
            data = json.dumps(body).encode()
            req = urllib.request.Request(
                f"{BASE}/api/chat/completions",
                data=data,
                headers={
                    "Authorization": f"Bearer {get_token()}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=120)

            content = ""
            tool_calls_accum = {}

            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                if "sources" in chunk and "choices" not in chunk:
                    continue

                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                finish = choices[0].get("finish_reason")

                if delta.get("content"):
                    content += delta["content"]

                if delta.get("tool_calls"):
                    for tc in delta.get("tool_calls", []):
                        tc_id = tc.get("id", f"tc_{len(tool_calls_accum)}")
                        if tc_id not in tool_calls_accum:
                            tool_calls_accum[tc_id] = {"name": "", "arguments": ""}
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            tool_calls_accum[tc_id]["name"] = fn["name"]
                        if fn.get("arguments"):
                            tool_calls_accum[tc_id]["arguments"] += fn["arguments"]

                if finish in ("stop", "tool_calls"):
                    break

            all_content += content

            if not tool_calls_accum:
                break

            # Execute tool calls
            messages = body.get("messages", [])
            messages.append({"role": "assistant", "content": content or None, "tool_calls": [
                {"id": tc_id, "type": "function",
                 "function": {"name": d["name"], "arguments": d["arguments"]}}
                for tc_id, d in tool_calls_accum.items()
            ]})

            for tc_id, tc_data in tool_calls_accum.items():
                tool_name = tc_data["name"]
                try:
                    tool_args = json.loads(tc_data["arguments"])
                except Exception:
                    tool_args = {}

                result = _dispatch_tool(tool_name, tool_args)

                messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})

            body = dict(body)
            body["messages"] = messages

        return all_content[:8000] if all_content else f"Sub-agent '{agent_id}' returned empty."

    except Exception as e:
        return f"Delegate error: {e}"


def _dispatch_tool(tool_name, tool_args):
    """Route a tool call to the right execute function. Shared by stream_chat and delegate_to."""
    if tool_name == "search_web":
        return execute_search_web(tool_args.get("query", ""))
    elif tool_name == "fetch_url":
        return execute_fetch_url(tool_args.get("url", ""))
    elif tool_name == "get_current_timestamp":
        return execute_get_current_timestamp()
    elif tool_name == "deep_research":
        return execute_deep_research(tool_args.get("query", ""), tool_args.get("depth", 3), tool_args.get("mode", "detailed"))
    elif tool_name == "search_and_read":
        return execute_search_and_read(tool_args.get("query", ""), tool_args.get("max_results", 3))
    elif tool_name == "ask_ai":
        return execute_ask_ai(tool_args.get("query", ""), tool_args.get("mode", "concise"))
    elif tool_name == "execute_bash":
        return execute_bash(tool_args.get("command", ""), tool_args.get("host", "local"))
    elif tool_name == "read_file":
        return execute_read_file(tool_args.get("path", ""))
    elif tool_name == "write_file":
        return execute_write_file(tool_args.get("path", ""), tool_args.get("content", ""))
    elif tool_name == "edit_file":
        return execute_edit_file(tool_args.get("path", ""), tool_args.get("old_text", ""), tool_args.get("new_text", ""))
    elif tool_name == "list_directory":
        return execute_list_directory(tool_args.get("path", ""))
    elif tool_name == "browse_page":
        return execute_browse_page(tool_args.get("url", ""))
    elif tool_name == "screenshot":
        return execute_screenshot()
    elif tool_name == "click_element":
        return execute_click_element(tool_args.get("selector", ""))
    elif tool_name == "type_text":
        return execute_type_text(tool_args.get("selector", ""), tool_args.get("text", ""))
    elif tool_name == "extract_data":
        return execute_extract_data(tool_args.get("expression", ""))
    elif tool_name == "analyze_image":
        return execute_analyze_image(tool_args.get("image_source", ""), tool_args.get("prompt", "Describe this image"))
    elif tool_name == "generate_image":
        return execute_generate_image(tool_args.get("prompt", ""), tool_args.get("width", 1024), tool_args.get("height", 1024))
    elif tool_name == "graph_search":
        return execute_graph_search(tool_args.get("query", ""), tool_args.get("limit", 10))
    elif tool_name == "graph_stats":
        return execute_graph_stats()
    elif tool_name == "entity_graph":
        return execute_entity_graph(tool_args.get("entity_name", ""), tool_args.get("depth", 2))
    elif tool_name == "list_tags":
        return execute_list_tags()
    elif tool_name == "list_spaces":
        return execute_list_spaces()
    elif tool_name == "list_conversations":
        return execute_list_conversations()
    elif tool_name == "vault_list":
        return execute_vault_list(tool_args.get("path", ""))
    elif tool_name == "vault_read":
        return execute_vault_read(tool_args.get("path", ""))
    elif tool_name == "vault_write":
        return execute_vault_write(tool_args.get("path", ""), tool_args.get("content", ""))
    elif tool_name == "vault_search":
        return execute_vault_search(tool_args.get("query", ""), tool_args.get("max_results", 10))
    elif tool_name == "create_artifact":
        return execute_create_artifact(tool_args.get("title", "Untitled"), tool_args.get("source", ""), tool_args.get("type", "html"))
    elif tool_name == "list_artifacts":
        return execute_list_artifacts()
    elif tool_name == "update_artifact":
        return execute_update_artifact(tool_args.get("id", ""), tool_args.get("source", ""))
    elif tool_name == "skill_list":
        return execute_skill_list()
    elif tool_name == "skill_load":
        return execute_skill_load(tool_args.get("name", ""))
    elif tool_name == "skill_execute":
        return execute_skill_execute(tool_args.get("name", ""), tool_args.get("variables", ""))
    elif tool_name == "agent_list":
        return execute_agent_list()
    elif tool_name == "agent_load":
        return execute_agent_load(tool_args.get("name", ""))
    elif tool_name == "agent_create":
        return execute_agent_create(
            tool_args.get("name", ""),
            tool_args.get("description", ""),
            tool_args.get("tools", ""),
            tool_args.get("system_prompt", ""),
            tool_args.get("model", ""),
        )
    elif tool_name == "agent_delete":
        return execute_agent_delete(tool_args.get("name", ""))
    elif tool_name == "thinking_log":
        return execute_thinking_log(
            tool_args.get("title", ""),
            tool_args.get("reasoning", ""),
            tool_args.get("conclusion", ""),
        )
    elif tool_name == "workflow_create":
        return execute_workflow_create(tool_args.get("name", ""), tool_args.get("nodes", "[]"), tool_args.get("connections", "{}"), tool_args.get("active", False))
    elif tool_name == "workflow_list":
        return execute_workflow_list()
    elif tool_name == "workflow_run":
        return execute_workflow_run(tool_args.get("workflow_id", ""), tool_args.get("data", "{}"))
    elif tool_name == "workflow_status":
        return execute_workflow_status(tool_args.get("workflow_id", ""), tool_args.get("limit", 10))
    elif tool_name == "workflow_delete":
        return execute_workflow_delete(tool_args.get("workflow_id", ""))
    elif tool_name == "signin_start":
        return execute_signin_start(tool_args.get("url", ""), tool_args.get("username", ""), tool_args.get("password", ""))
    elif tool_name == "signin_auto":
        return execute_signin_auto(tool_args.get("name", ""))
    elif tool_name == "signin_status":
        return execute_signin_status()
    elif tool_name == "signin_submit_2fa":
        return execute_signin_submit_2fa(tool_args.get("code", ""))
    elif tool_name == "signin_check_2fa":
        return execute_signin_check_2fa()
    elif tool_name == "signin_save":
        return execute_signin_save(tool_args.get("name", ""), tool_args.get("url", ""), tool_args.get("username", ""), tool_args.get("password", ""), tool_args.get("totp_secret", ""), tool_args.get("selectors", ""))
    elif tool_name == "macro_record_start":
        return execute_macro_record_start(tool_args.get("name", ""), tool_args.get("url", ""))
    elif tool_name == "macro_record_stop":
        return execute_macro_record_stop()
    elif tool_name == "macro_record_browser":
        return execute_macro_record_browser(tool_args.get("name", ""), tool_args.get("url", ""))
    elif tool_name == "macro_record_stop_browser":
        return execute_macro_record_stop_browser()
    elif tool_name == "macro_play":
        return execute_macro_play(tool_args.get("macro_id", 0))
    elif tool_name == "macro_list":
        return execute_macro_list()
    elif tool_name == "youtube_play":
        return execute_youtube_play(tool_args.get("query", ""))
    elif tool_name == "play_video":
        return execute_play_video(tool_args.get("url", ""))
    elif tool_name == "read_url":
        return execute_read_url(tool_args.get("url", ""), tool_args.get("format", "markdown"))
    elif tool_name == "upload_file":
        return execute_upload_file(tool_args.get("file_path", ""), tool_args.get("query", ""))
    elif tool_name == "download_save":
        return execute_download_save(tool_args.get("url", ""), tool_args.get("filename", ""), tool_args.get("subdir", ""))
    elif tool_name == "download_list":
        return execute_download_list(tool_args.get("subdir", ""))
    else:
        return f"Tool '{tool_name}' not implemented."


def _slugify(text, max_len=50):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:max_len]


def _get_recent_chats(token, limit=5):
    """Get recent chat titles for system prompt context."""
    try:
        result = api("GET", "/api/v1/chats/?page=0", token)
        if not isinstance(result, list):
            return []
        chats = []
        for c in result[:limit]:
            chats.append({
                "title": c.get("title", "untitled"),
                "date": time.strftime("%Y-%m-%d", time.localtime(c.get("updated_at", 0) / 1000)),
            })
        return chats
    except Exception:
        return []


def _get_chat_messages(token, chat_id):
    """Fetch full chat messages from OpenWebUI."""
    try:
        chat = api("GET", f"/api/v1/chats/{chat_id}", token)
        if "error" in chat:
            return []
        msgs = chat.get("history", {}).get("messages", {})
        sorted_msgs = sorted(msgs.values(), key=lambda m: m.get("timestamp", 0))
        return sorted_msgs
    except Exception:
        return []


def log_chat_to_vault(token, chat_id, user_message, agent_response, tool_names=None, sources=None):
    """Log a completed chat to the Obsidian vault using Jinja2 template."""
    try:
        # Get chat title from OpenWebUI
        chat = api("GET", f"/api/v1/chats/{chat_id}", token)
        title = "untitled"
        ow_messages = []
        if not isinstance(chat, dict) or "error" not in chat:
            title = chat.get("title", "untitled")
            msgs_raw = chat.get("history", {}).get("messages", {})
            sorted_msgs = sorted(msgs_raw.values(), key=lambda m: m.get("timestamp", 0))
            for m in sorted_msgs:
                role = m.get("role", "?")
                content = m.get("content", "")
                if role == "assistant":
                    content = strip_reasoning(content)
                tc = m.get("tool_calls") or (m.get("metadata") or {}).get("tool_calls")
                entry = {"role": role, "content": content[:2000]}
                if tc:
                    entry["tool_calls"] = [t.get("function", {}).get("name", "?") for t in tc]
                ow_messages.append(entry)

        # Always include the current exchange if OW messages empty
        if not ow_messages:
            ow_messages = [
                {"role": "user", "content": user_message[:2000]},
                {"role": "assistant", "content": agent_response[:2000]},
            ]

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        today = time.strftime("%Y-%m-%d")

        # Render chat note with Jinja2
        template = _jinja_env.get_template("chat_note.j2")
        note = template.render(
            created=now,
            updated=now,
            user=_current_user,
            user_tag=_current_user,
            extra_tags=[],
            model=MODEL,
            chat_id=chat_id,
            tool_calls=tool_names or [],
            message_count=len(ow_messages),
            title=title,
            messages=ow_messages,
            sources=[{"name": s.get("name", ""), "url": s.get("urls", [""])[0]}
                     for s in (sources or [])] if sources else [],
            tool_names=tool_names or [],
        )

        # Save to vault/chats/{user}/{date}-{slug}.md
        slug = _slugify(title) or "chat"
        filename = f"{today}-{slug}.md"
        chat_dir = os.path.join(VAULT_ROOT, "chats", _current_user)
        os.makedirs(chat_dir, exist_ok=True)

        # Append counter if duplicate
        filepath = os.path.join(chat_dir, filename)
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(chat_dir, f"{today}-{slug}-{counter}.md")
            counter += 1

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(note)

        return filepath
    except Exception as e:
        return f"Log error: {e}"


def render_system_prompt(token):
    """Render dynamic system prompt using Jinja2 with context."""
    try:
        template = _jinja_env.get_template("system_prompt.j2")
        recent = _get_recent_chats(token, limit=5)
        agents = _get_agent_summaries()
        return template.render(
            model=MODEL,
            user=_current_user,
            session_date=time.strftime("%Y-%m-%d %H:%M"),
            recent_chats=recent,
            agents=agents,
        )
    except Exception as e:
        return f"System prompt render error: {e}"


def stream_chat(token, body):
    """Send streaming chat request with agent loop (handles tool calls)."""
    max_loops = 25
    all_content = ""
    all_reasoning = ""
    all_sources = []
    all_tool_names = []

    for loop in range(max_loops):
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{BASE}/api/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=MAX_POLL)

        content = ""
        reasoning = ""
        tool_calls_accum = {}  # id -> {name, arguments}

        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue

            # Standalone sources event
            if "sources" in chunk and "choices" not in chunk:
                for src in chunk.get("sources", []):
                    s = src.get("source", src)
                    all_sources.append({
                        "name": s.get("name", ""),
                        "urls": s.get("urls", []),
                        "queries": s.get("queries", []),
                    })
                continue

            choices = chunk.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            finish = choices[0].get("finish_reason")

            if delta.get("content"):
                content += delta["content"]
            if delta.get("reasoning_content"):
                reasoning += delta["reasoning_content"]

            # Accumulate tool calls
            if delta.get("tool_calls"):
                for tc in delta["tool_calls"]:
                    tc_id = tc.get("id", f"tc_{len(tool_calls_accum)}")
                    if tc_id not in tool_calls_accum:
                        tool_calls_accum[tc_id] = {"name": "", "arguments": ""}
                    fn = tc.get("function", {})
                    if fn.get("name"):
                        tool_calls_accum[tc_id]["name"] = fn["name"]
                    if fn.get("arguments"):
                        tool_calls_accum[tc_id]["arguments"] += fn["arguments"]

            if finish in ("stop", "tool_calls"):
                break

        all_content += content
        all_reasoning += reasoning

        # If no tool calls, we're done
        if not tool_calls_accum:
            break

        # Execute tool calls and build continuation messages
        messages = body.get("messages", [])
        # Add assistant message with tool calls
        assistant_msg = {"role": "assistant", "content": content or None, "tool_calls": []}
        for tc_id, tc_data in tool_calls_accum.items():
            assistant_msg["tool_calls"].append({
                "id": tc_id,
                "type": "function",
                "function": {"name": tc_data["name"], "arguments": tc_data["arguments"]},
            })
            if tc_data["name"] not in all_tool_names:
                all_tool_names.append(tc_data["name"])
        messages.append(assistant_msg)

        # Execute each tool and add results
        for tc_id, tc_data in tool_calls_accum.items():
            tool_name = tc_data["name"]
            try:
                tool_args = json.loads(tc_data["arguments"])
            except:
                tool_args = {}

            if tool_name == "search_web":
                query = tool_args.get("query", "")
                result = execute_search_web(query)
            elif tool_name == "fetch_url":
                url = tool_args.get("url", "")
                result = execute_fetch_url(url)
            elif tool_name == "get_current_timestamp":
                result = execute_get_current_timestamp()
            elif tool_name == "deep_research":
                result = execute_deep_research(
                    tool_args.get("query", ""),
                    tool_args.get("depth", 3),
                    tool_args.get("mode", "detailed"),
                )
            elif tool_name == "search_and_read":
                result = execute_search_and_read(
                    tool_args.get("query", ""),
                    tool_args.get("max_results", 3),
                )
            elif tool_name == "ask_ai":
                result = execute_ask_ai(
                    tool_args.get("query", ""),
                    tool_args.get("mode", "concise"),
                )
            elif tool_name == "execute_bash":
                result = execute_bash(
                    tool_args.get("command", ""),
                    tool_args.get("host", "local"),
                )
            elif tool_name == "read_file":
                result = execute_read_file(tool_args.get("path", ""))
            elif tool_name == "write_file":
                result = execute_write_file(tool_args.get("path", ""), tool_args.get("content", ""))
            elif tool_name == "edit_file":
                result = execute_edit_file(
                    tool_args.get("path", ""),
                    tool_args.get("old_text", ""),
                    tool_args.get("new_text", ""),
                )
            elif tool_name == "list_directory":
                result = execute_list_directory(tool_args.get("path", ""))
            elif tool_name == "browse_page":
                result = execute_browse_page(tool_args.get("url", ""))
            elif tool_name == "screenshot":
                result = execute_screenshot()
            elif tool_name == "click_element":
                result = execute_click_element(tool_args.get("selector", ""))
            elif tool_name == "type_text":
                result = execute_type_text(tool_args.get("selector", ""), tool_args.get("text", ""))
            elif tool_name == "extract_data":
                result = execute_extract_data(tool_args.get("expression", ""))
            elif tool_name == "analyze_image":
                result = execute_analyze_image(
                    tool_args.get("image_source", ""),
                    tool_args.get("prompt", "Describe this image in detail"),
                )
            elif tool_name == "generate_image":
                result = execute_generate_image(
                    tool_args.get("prompt", ""),
                    tool_args.get("width", 1024),
                    tool_args.get("height", 1024),
                )
            elif tool_name == "graph_search":
                result = execute_graph_search(
                    tool_args.get("query", ""),
                    tool_args.get("limit", 10),
                )
            elif tool_name == "graph_stats":
                result = execute_graph_stats()
            elif tool_name == "entity_graph":
                result = execute_entity_graph(
                    tool_args.get("entity_name", ""),
                    tool_args.get("depth", 2),
                )
            elif tool_name == "list_tags":
                result = execute_list_tags()
            elif tool_name == "list_spaces":
                result = execute_list_spaces()
            elif tool_name == "list_conversations":
                result = execute_list_conversations()
            elif tool_name == "mermaid_diagram":
                # Graph visuals — generate Mermaid syntax (no API call needed)
                diagram_type = tool_args.get("diagram_type", "flowchart")
                title = tool_args.get("title", "")
                items = tool_args.get("items", "")
                lines = ["flowchart TD"]
                if title:
                    lines.append(f"    title[{title}]")
                for line in items.replace("\\n", "\n").strip().split("\n"):
                    line = line.strip()
                    if line:
                        lines.append(f"    {line}")
                result = "\n".join(lines)
            elif tool_name == "entity_network":
                entities = tool_args.get("entities", "")
                title = tool_args.get("title", "Entity Network")
                lines = ["graph TD", f"    subgraph {title}"]
                for item in entities.split(","):
                    item = item.strip()
                    if "-->" in item or "---" in item:
                        lines.append(f"    {item}")
                    elif item:
                        nid = item.replace(" ", "_").replace("-", "_")
                        lines.append(f"    {nid}[{item}]")
                lines.append("    end")
                result = "\n".join(lines)
            elif tool_name == "vault_list":
                result = execute_vault_list(tool_args.get("path", ""))
            elif tool_name == "vault_read":
                result = execute_vault_read(tool_args.get("path", ""))
            elif tool_name == "vault_write":
                result = execute_vault_write(tool_args.get("path", ""), tool_args.get("content", ""))
            elif tool_name == "vault_search":
                result = execute_vault_search(tool_args.get("query", ""), tool_args.get("max_results", 10))
            elif tool_name == "speech_to_text":
                result = execute_speech_to_text(
                    tool_args.get("audio_base64", ""),
                    tool_args.get("language", None),
                )
            elif tool_name == "text_to_speech":
                result = execute_text_to_speech(
                    tool_args.get("text", ""),
                    tool_args.get("voice", "af_bella"),
                    tool_args.get("speed", 1.0),
                )
            elif tool_name == "create_artifact":
                result = execute_create_artifact(
                    tool_args.get("title", "Untitled"),
                    tool_args.get("source", ""),
                    tool_args.get("type", "html"),
                )
            elif tool_name == "list_artifacts":
                result = execute_list_artifacts()
            elif tool_name == "update_artifact":
                result = execute_update_artifact(
                    tool_args.get("id", ""),
                    tool_args.get("source", ""),
                )
            elif tool_name == "skill_list":
                result = execute_skill_list()
            elif tool_name == "skill_load":
                result = execute_skill_load(tool_args.get("name", ""))
            elif tool_name == "skill_execute":
                result = execute_skill_execute(
                    tool_args.get("name", ""),
                    tool_args.get("variables", ""),
                )
            elif tool_name == "agent_list":
                result = execute_agent_list()
            elif tool_name == "agent_load":
                result = execute_agent_load(tool_args.get("name", ""))
            elif tool_name == "agent_create":
                result = execute_agent_create(
                    tool_args.get("name", ""),
                    tool_args.get("description", ""),
                    tool_args.get("tools", ""),
                    tool_args.get("system_prompt", ""),
                    tool_args.get("model", ""),
                )
            elif tool_name == "agent_delete":
                result = execute_agent_delete(tool_args.get("name", ""))
            elif tool_name == "thinking_log":
                result = execute_thinking_log(
                    tool_args.get("title", ""),
                    tool_args.get("reasoning", ""),
                    tool_args.get("conclusion", ""),
                )
            elif tool_name == "workflow_create":
                result = execute_workflow_create(tool_args.get("name", ""), tool_args.get("nodes", "[]"), tool_args.get("connections", "{}"), tool_args.get("active", False))
            elif tool_name == "workflow_list":
                result = execute_workflow_list()
            elif tool_name == "workflow_run":
                result = execute_workflow_run(tool_args.get("workflow_id", ""), tool_args.get("data", "{}"))
            elif tool_name == "workflow_status":
                result = execute_workflow_status(tool_args.get("workflow_id", ""), tool_args.get("limit", 10))
            elif tool_name == "workflow_delete":
                result = execute_workflow_delete(tool_args.get("workflow_id", ""))
            elif tool_name == "signin_start":
                result = execute_signin_start(tool_args.get("url", ""), tool_args.get("username", ""), tool_args.get("password", ""))
            elif tool_name == "signin_auto":
                result = execute_signin_auto(tool_args.get("name", ""))
            elif tool_name == "signin_submit_2fa":
                result = execute_signin_submit_2fa(tool_args.get("code", ""))
            elif tool_name == "signin_check_2fa":
                result = execute_signin_check_2fa()
            elif tool_name == "signin_save":
                result = execute_signin_save(tool_args.get("name", ""), tool_args.get("url", ""), tool_args.get("username", ""), tool_args.get("password", ""), tool_args.get("totp_secret", ""))
            elif tool_name == "macro_record_start":
                result = execute_macro_record_start(tool_args.get("name", ""), tool_args.get("url", ""))
            elif tool_name == "macro_record_stop":
                result = execute_macro_record_stop()
            elif tool_name == "macro_play":
                result = execute_macro_play(tool_args.get("macro_id", 0))
            elif tool_name == "macro_list":
                result = execute_macro_list()
            elif tool_name == "youtube_play":
                result = execute_youtube_play(tool_args.get("query", ""))
            elif tool_name == "play_video":
                result = execute_play_video(tool_args.get("url", ""))
            elif tool_name == "read_url":
                result = execute_read_url(tool_args.get("url", ""))
            elif tool_name == "upload_file":
                result = execute_upload_file(tool_args.get("file_path", ""), tool_args.get("query", ""))
            elif tool_name == "download_save":
                result = execute_download_save(tool_args.get("url", ""), tool_args.get("filename", ""), tool_args.get("subdir", ""))
            elif tool_name == "download_list":
                result = execute_download_list(tool_args.get("subdir", ""))
            elif tool_name == "delegate_to":
                result = execute_delegate_to(
                    tool_args.get("agent_id", ""),
                    tool_args.get("message", ""),
                )
            else:
                result = f"Tool '{tool_name}' not implemented in MCP."

            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            })

        # Update body for next loop
        body = dict(body)
        body["messages"] = messages

    return all_content, all_reasoning, all_sources, all_tool_names


# Custom tool function schemas — injected into request so the model sees them
CUSTOM_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "deep_research",
            "description": "Multi-round deep research on a complex topic. Returns comprehensive report with sources.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "depth": {"type": "integer", "default": 3},
                "mode": {"type": "string", "default": "detailed"},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_and_read",
            "description": "Search the web and read top results in one call.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "max_results": {"type": "integer", "default": 3},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_ai",
            "description": "Consult another AI model for a second opinion.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "mode": {"type": "string", "default": "concise"},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Execute a bash command. host='local' for Rog, host='lappy' for Lappy (192.168.0.33).",
            "parameters": {"type": "object", "properties": {
                "command": {"type": "string"}, "host": {"type": "string", "default": "local"},
            }, "required": ["command"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file's contents.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
            }, "required": ["path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}, "content": {"type": "string"},
            }, "required": ["path", "content"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing text.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"},
            }, "required": ["path", "old_text", "new_text"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories at a path.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "default": "."},
            }},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browse_page",
            "description": "Navigate to a URL and return page content.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"},
            }, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot of the current browser page.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "Click an element by CSS selector.",
            "parameters": {"type": "object", "properties": {
                "selector": {"type": "string"},
            }, "required": ["selector"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into an element.",
            "parameters": {"type": "object", "properties": {
                "selector": {"type": "string"}, "text": {"type": "string"},
            }, "required": ["selector", "text"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_data",
            "description": "Extract data from the page using a JavaScript expression.",
            "parameters": {"type": "object", "properties": {
                "expression": {"type": "string"},
            }, "required": ["expression"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_image",
            "description": "Analyze an image URL.",
            "parameters": {"type": "object", "properties": {
                "image_source": {"type": "string"}, "prompt": {"type": "string"},
            }, "required": ["image_source"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image using ComfyUI.",
            "parameters": {"type": "object", "properties": {
                "prompt": {"type": "string"}, "width": {"type": "integer", "default": 1024},
                "height": {"type": "integer", "default": 1024},
            }, "required": ["prompt"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "graph_search",
            "description": "Full-text search across conversations and entities in the knowledge graph.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "limit": {"type": "integer", "default": 10},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "graph_stats",
            "description": "Get knowledge graph statistics.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "entity_graph",
            "description": "Get an entity with its neighbors from the knowledge graph.",
            "parameters": {"type": "object", "properties": {
                "entity_name": {"type": "string"}, "depth": {"type": "integer", "default": 2},
            }, "required": ["entity_name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tags",
            "description": "List all tags in the knowledge graph.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_spaces",
            "description": "List all knowledge graph spaces.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_conversations",
            "description": "List all conversations in the knowledge graph.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mermaid_diagram",
            "description": "Generate Mermaid diagram syntax from structured data.",
            "parameters": {"type": "object", "properties": {
                "diagram_type": {"type": "string"}, "title": {"type": "string"},
                "items": {"type": "string"},
            }, "required": ["items"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "entity_network",
            "description": "Generate entity network diagram syntax.",
            "parameters": {"type": "object", "properties": {
                "entities": {"type": "string"}, "title": {"type": "string", "default": "Entity Network"},
            }, "required": ["entities"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vault_list",
            "description": "List files in the Obsidian vault.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "default": ""},
            }},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vault_read",
            "description": "Read a file from the Obsidian vault.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
            }, "required": ["path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vault_write",
            "description": "Write a file to the Obsidian vault.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}, "content": {"type": "string"},
            }, "required": ["path", "content"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vault_search",
            "description": "Full-text search across vault notes.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "max_results": {"type": "integer", "default": 10},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_artifact",
            "description": "Create a sandboxed code artifact (HTML/SVG/React/JS/Mermaid/Python/CSS preview). Returns artifact ID and URL.",
            "parameters": {"type": "object", "properties": {
                "title": {"type": "string", "description": "Display title"},
                "source": {"type": "string", "description": "Source code"},
                "type": {"type": "string", "description": "html/svg/react/javascript/mermaid/python/code/css", "default": "html"},
            }, "required": ["source"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_artifacts",
            "description": "List all stored artifacts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_artifact",
            "description": "Update an artifact's source code.",
            "parameters": {"type": "object", "properties": {
                "id": {"type": "string"}, "source": {"type": "string"},
            }, "required": ["id", "source"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_list",
            "description": "List all available skills (reusable prompt templates).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_load",
            "description": "Load a skill template to see its content and variables.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Skill name (e.g. landing-page, chart, form, email-draft, report, summarize)"},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_execute",
            "description": "Execute a skill: render template with variables and return the prompt. Use for reusable workflows.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Skill name"},
                "variables": {"type": "string", "description": "JSON or key=value pairs for template variables"},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to",
            "description": "Delegate a task to a sub-agent. Use agent_list first to see available agents and their tools. Sends the message to the sub-agent and returns its response.",
            "parameters": {"type": "object", "properties": {
                "agent_id": {"type": "string", "description": "Agent slug (e.g. researcher, coder, writer)"},
                "message": {"type": "string", "description": "The task/message to send to the sub-agent"},
            }, "required": ["agent_id", "message"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agent_list",
            "description": "List all available template-based agents with their tools and model overrides.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agent_load",
            "description": "Load an agent template to see its full system prompt, tools, and configuration.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Agent name/slug (e.g. researcher, coder, writer)"},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agent_create",
            "description": "Create a new agent template in vault/agents/. The agent becomes immediately available for delegation and as an MCP tool.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Display name for the agent"},
                "description": {"type": "string", "description": "What the agent does"},
                "tools": {"type": "string", "description": "Comma-separated tool names from CUSTOM_TOOL_SCHEMAS"},
                "system_prompt": {"type": "string", "description": "Jinja2 system prompt body. Variables: {{ task }}, {{ agent_name }}, {{ date }}"},
                "model": {"type": "string", "description": "Optional model override"},
            }, "required": ["name", "description", "tools", "system_prompt"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agent_delete",
            "description": "Delete an agent template from vault/agents/.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Agent name/slug to delete"},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "thinking_log",
            "description": "Save a reasoning trace or chain-of-thought to vault/thinking/ for transparency. Use this for complex multi-step reasoning to make your thought process auditable.",
            "parameters": {"type": "object", "properties": {
                "title": {"type": "string", "description": "Short title for the reasoning trace"},
                "reasoning": {"type": "string", "description": "The full reasoning chain, step-by-step"},
                "conclusion": {"type": "string", "description": "Final conclusion or decision (optional)"},
            }, "required": ["title", "reasoning"]},
        },
    },
    # --- Alphabetty extended tools ---
    {
        "type": "function",
        "function": {
            "name": "workflow_create",
            "description": "Create an n8n workflow from JSON nodes and connections.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"}, "nodes": {"type": "string", "description": "JSON array of nodes"},
                "connections": {"type": "string", "description": "JSON object mapping node names to connections"},
                "active": {"type": "boolean", "default": False},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workflow_list",
            "description": "List all n8n workflows.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workflow_run",
            "description": "Trigger a workflow execution.",
            "parameters": {"type": "object", "properties": {
                "workflow_id": {"type": "string"}, "data": {"type": "string", "default": "{}"},
            }, "required": ["workflow_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workflow_status",
            "description": "Check execution history for a workflow.",
            "parameters": {"type": "object", "properties": {
                "workflow_id": {"type": "string"}, "limit": {"type": "integer", "default": 10},
            }, "required": ["workflow_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workflow_delete",
            "description": "Delete an n8n workflow.",
            "parameters": {"type": "object", "properties": {
                "workflow_id": {"type": "string"},
            }, "required": ["workflow_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "signin_start",
            "description": "Start a sign-in flow for a website.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}, "username": {"type": "string"}, "password": {"type": "string"},
            }, "required": ["url", "username", "password"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "signin_auto",
            "description": "Auto sign-in using saved credentials.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Profile name (e.g. google, github)"},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "signin_save",
            "description": "Save credential profile for auto sign-in.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"}, "url": {"type": "string"},
                "username": {"type": "string"}, "password": {"type": "string"},
                "totp_secret": {"type": "string", "default": ""},
            }, "required": ["name", "url", "username", "password"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "macro_record_start",
            "description": "Start recording browser macro.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"}, "url": {"type": "string", "default": ""},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "macro_record_stop",
            "description": "Stop macro recording and save.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "macro_play",
            "description": "Replay a saved macro.",
            "parameters": {"type": "object", "properties": {
                "macro_id": {"type": "integer"},
            }, "required": ["macro_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "macro_list",
            "description": "List saved macros.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_play",
            "description": "Search YouTube and play in browser.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_video",
            "description": "Play a video URL in browser.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"},
            }, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Fetch and convert URL to text/markdown via Alphabetty.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}, "format": {"type": "string", "default": "markdown"},
            }, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upload_file",
            "description": "Upload a file from local path for analysis.",
            "parameters": {"type": "object", "properties": {
                "file_path": {"type": "string"}, "query": {"type": "string", "default": ""},
            }, "required": ["file_path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_save",
            "description": "Download a file from URL and save to server.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}, "filename": {"type": "string", "default": ""},
                "subdir": {"type": "string", "default": ""},
            }, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_list",
            "description": "List files in server download directory.",
            "parameters": {"type": "object", "properties": {
                "subdir": {"type": "string", "default": ""},
            }},
        },
    },
]


def find_real_chat_id(token, fallback=""):
    """Find the most recent chat UUID from OpenWebUI."""
    result = api("GET", "/api/v1/chats/?page=0", token)
    if isinstance(result, list) and result:
        return result[0]["id"]
    return fallback


def tool_chat(message: str, chat_id: str = "", web_search: bool = True,
              user_email: str = "", user_password: str = "") -> dict:
    """Send a message to sloth-agent via streaming and wait for full response with tool execution.

    Args:
        message: Message to send
        chat_id: Existing chat ID to continue (optional)
        web_search: Enable web search (default True)
        user_email: Authenticate as this user (default: main admin)
        user_password: Password for the user
    """
    global _current_user
    if user_email:
        token = get_token_for(user_email, user_password or "Sloth2026!")
        _current_user = user_email.split("@")[0]
    else:
        token = get_token()
        _current_user = "aaron"

    msg_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    # Render dynamic system prompt via Jinja2
    system_prompt = render_system_prompt(token)

    body = {
        "chat_id": chat_id,
        "id": msg_id,
        "messages": [{"role": "user", "content": message}],
        "model": MODEL,
        "stream": True,
        "session_id": session_id,
        "system": system_prompt,
        "tools": CUSTOM_TOOL_SCHEMAS,
        "tool_ids": ["alphabetty", "bash_tool", "file_system", "browser_control", "vision", "knowledge_graph", "graph_visuals", "obsidian", "voice", "artifacts", "skills"],
        "features": {
            "web_search": web_search,
        },
    }

    content, reasoning, sources, tool_names = stream_chat(token, body)

    # Strip <details> blocks for clean response
    clean = strip_reasoning(content)

    # Resolve real chat UUID (OpenWebUI creates it on first message)
    real_chat_id = chat_id
    if not chat_id:
        real_chat_id = find_real_chat_id(token, msg_id)

    # Auto-log chat to vault
    log_path = log_chat_to_vault(token, real_chat_id, message, clean, tool_names, sources)

    result = {
        "response": clean,
        "reasoning": reasoning[:500] if reasoning else "",
        "chat_id": real_chat_id,
        "finish_reason": "stop",
        "tool_calls": tool_names,
    }
    if sources:
        result["sources"] = sources[:10]
    if isinstance(log_path, str) and not log_path.startswith("Log error"):
        result["vault_log"] = log_path
    return result


def tool_read(chat_id: str = "", limit: int = 10) -> dict:
    """Read chat history. If no chat_id, reads the latest chat."""
    token = get_token()

    if not chat_id:
        result = api("GET", "/api/v1/chats/?page=0", token)
        if "error" in result or not result:
            return {"error": "No chats found"}
        chat_id = result[0]["id"]

    chat = api("GET", f"/api/v1/chats/{chat_id}", token)
    if "error" in chat:
        return chat

    title = chat.get("title", "untitled")
    messages = chat.get("history", {}).get("messages", {})
    sorted_msgs = sorted(messages.values(), key=lambda m: m.get("timestamp", 0))

    # Limit to last N messages
    if limit > 0:
        sorted_msgs = sorted_msgs[-limit:]

    history = []
    for msg in sorted_msgs:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        done = msg.get("done", True)

        entry = {"role": role}
        if role == "assistant":
            entry["content"] = strip_reasoning(content)
            entry["done"] = done
            tc = msg.get("tool_calls") or (msg.get("metadata") or {}).get("tool_calls")
            if tc:
                entry["tool_calls"] = [t.get("function", {}).get("name", "?") for t in tc]
        else:
            entry["content"] = content[:1000]
        history.append(entry)

    return {"chat_id": chat_id, "title": title, "messages": history}


def tool_list_chats() -> dict:
    """List all OpenWebUI chats."""
    token = get_token()
    result = api("GET", "/api/v1/chats/?page=0", token)
    if "error" in result:
        return result

    chats = []
    for chat in result:
        updated = chat.get("updated_at", 0)
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(updated / 1000)) if updated else "?"
        chats.append({
            "id": chat["id"],
            "title": chat.get("title", "untitled"),
            "updated": ts,
        })
    return {"chats": chats}


def tool_models() -> dict:
    """List available models in OpenWebUI."""
    token = get_token()
    # /api/models returns {"data": [...]}
    result = api("GET", "/api/models", token)
    if "error" in result:
        return result
    models = result.get("data", [])
    out = []
    for m in models:
        mid = m.get("id", "?")
        name = m.get("name", mid)
        base = (m.get("info") or {}).get("base_model_id", "")
        out.append({"id": mid, "name": name, "base_model_id": base})
    return {"models": out}


def tool_delete_chat(chat_id: str) -> dict:
    """Delete a chat by ID."""
    token = get_token()
    result = api("DELETE", f"/api/v1/chats/{chat_id}", token)
    if "error" in result:
        return result
    return {"deleted": True, "chat_id": chat_id}


def tool_update_model(model_id: str, capabilities: str = "", function_calling: str = "",
                      web_search: str = "", tools: str = "") -> dict:
    """DISABLED — this tool corrupted the sloth-agent model config by nesting params inside meta.

    OpenWebUI has no proper model update API. Use DB-direct access instead:
      ssh aaron@192.168.0.33 'docker exec -i open-webui python3'
      import sqlite3, json; db = sqlite3.connect("/app/backend/data/webui.db")
      # read/modify model rows directly, then db.commit()
    """
    return {"error": "tool_update_model is DISABLED — it corrupted model configs. "
                     "Use DB-direct access via SSH to open-webui container. "
                     "See MEMORY.md for correct DB structure."}


def tool_get_config() -> dict:
    """Get current OpenWebUI retrieval/web search config."""
    token = get_token()
    return api("GET", "/api/v1/retrieval/config", token)


def tool_update_config(web_search: str = "", search_engine: str = "",
                       searxng_url: str = "") -> dict:
    """Update OpenWebUI global web search config via admin API."""
    token = get_token()

    body = {"web": {}}
    if web_search:
        body["web"]["ENABLE_WEB_SEARCH"] = web_search.lower() == "true"
    if search_engine:
        body["web"]["WEB_SEARCH_ENGINE"] = search_engine
    if searxng_url:
        body["web"]["SEARXNG_QUERY_URL"] = searxng_url

    return api("POST", "/api/v1/retrieval/config/update", token, body)


# --- MCP stdio protocol ---

TOOLS = {
    "openweb_chat": {
        "description": "Send a message to the sloth-agent in OpenWebUI and wait for the response. Uses streaming mode so tools (web search, etc.) actually execute. Returns the agent's reply, any tool calls used, and the chat_id for continuation. Supports multi-user — pass user_email to chat as a different user (chats are isolated per user, vault is shared).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to send to the agent"},
                "chat_id": {"type": "string", "description": "Existing chat ID to continue a conversation (optional)", "default": ""},
                "web_search": {"type": "boolean", "description": "Enable web search for this message (default: true)", "default": True},
                "user_email": {"type": "string", "description": "Authenticate as this user (default: main admin). Chats are isolated per user.", "default": ""},
                "user_password": {"type": "string", "description": "Password for the user account", "default": ""},
            },
            "required": ["message"],
        },
        "handler": lambda args: tool_chat(
            args["message"],
            args.get("chat_id", ""),
            args.get("web_search", True),
            args.get("user_email", ""),
            args.get("user_password", ""),
        ),
    },
    "openweb_read": {
        "description": "Read chat history from OpenWebUI. Shows recent messages with roles, content, and tool calls.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string", "description": "Chat ID to read (empty = latest chat)", "default": ""},
                "limit": {"type": "integer", "description": "Max messages to return (0 = all)", "default": 10},
            },
        },
        "handler": lambda args: tool_read(args.get("chat_id", ""), args.get("limit", 10)),
    },
    "openweb_list_chats": {
        "description": "List all OpenWebUI chats with titles and timestamps.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: tool_list_chats(),
    },
    "openweb_models": {
        "description": "List available models in OpenWebUI.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: tool_models(),
    },
    "openweb_delete_chat": {
        "description": "Delete an OpenWebUI chat by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string", "description": "Chat ID to delete"},
            },
            "required": ["chat_id"],
        },
        "handler": lambda args: tool_delete_chat(args["chat_id"]),
    },
    "openweb_update_model": {
        "description": "Update an OpenWebUI model's configuration (capabilities, function calling, web search, tools). Merges with existing config.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_id": {"type": "string", "description": "Model ID to update (e.g. 'sloth-agent')"},
                "capabilities": {"type": "string", "description": "Comma-separated key=true/false pairs (e.g. 'web_search=true,image_generation=false')"},
                "function_calling": {"type": "string", "description": "Function calling mode: 'native' or 'default'"},
                "web_search": {"type": "string", "description": "Enable web search feature: 'true' or 'false'"},
                "tools": {"type": "string", "description": "Comma-separated tool IDs to attach (e.g. 'web_search,url_fetcher,memory')"},
            },
            "required": ["model_id"],
        },
        "handler": lambda args: tool_update_model(
            args["model_id"],
            args.get("capabilities", ""),
            args.get("function_calling", ""),
            args.get("web_search", ""),
            args.get("tools", ""),
        ),
    },
    "openweb_get_config": {
        "description": "Get current OpenWebUI retrieval/web search config.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: tool_get_config(),
    },
    "openweb_create_artifact": {
        "description": "Create a sandboxed code artifact (HTML/SVG/React/JS/Mermaid/Python/CSS preview). Returns artifact ID and preview URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Display title for the artifact"},
                "source": {"type": "string", "description": "Source code (HTML, SVG, React JSX, JavaScript, Mermaid, Python, CSS)"},
                "type": {"type": "string", "description": "Artifact type: html, svg, react, javascript, mermaid, python, code, css", "default": "html"},
            },
            "required": ["source"],
        },
        "handler": lambda args: execute_create_artifact(
            args.get("title", "Untitled"),
            args["source"],
            args.get("type", "html"),
        ),
    },
    "openweb_list_artifacts": {
        "description": "List all stored artifacts with IDs, titles, types, and timestamps.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: execute_list_artifacts(),
    },
    "openweb_update_artifact": {
        "description": "Update the source code of an existing artifact.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Artifact ID"},
                "source": {"type": "string", "description": "New source code"},
            },
            "required": ["id", "source"],
        },
        "handler": lambda args: execute_update_artifact(args["id"], args["source"]),
    },
    "openweb_skill_list": {
        "description": "List all available skills (reusable prompt templates from vault/skills/).",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: execute_skill_list(),
    },
    "openweb_skill_load": {
        "description": "Load a skill template by name to see its content and variables.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name (e.g. 'landing-page', 'chart', 'email-draft')"},
            },
            "required": ["name"],
        },
        "handler": lambda args: execute_skill_load(args["name"]),
    },
    "openweb_skill_execute": {
        "description": "Execute a skill: renders the template with variables and returns the prompt. Use this to load a reusable workflow (e.g. landing page, chart, form, email draft).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name (e.g. 'landing-page', 'chart', 'form', 'email-draft', 'report', 'summarize')"},
                "variables": {"type": "string", "description": "JSON object or comma-separated key=value pairs for template variables. Example: '{\"topic\":\"SaaS product\",\"style\":\"minimal\"}' or 'topic=SaaS product,style=minimal'"},
            },
            "required": ["name"],
        },
        "handler": lambda args: execute_skill_execute(
            args["name"],
            args.get("variables", ""),
        ),
    },
    "openweb_agent_list": {
        "description": "List all available template-based agents with their tools, descriptions, and model overrides.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: execute_agent_list(),
    },
    "openweb_agent_load": {
        "description": "Load an agent template by name to see its full system prompt, tools, and configuration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Agent name/slug (e.g. 'researcher', 'coder', 'writer')"},
            },
            "required": ["name"],
        },
        "handler": lambda args: execute_agent_load(args["name"]),
    },
    "openweb_agent_create": {
        "description": "Create a new agent template in vault/agents/. The agent becomes immediately available for delegation and as an MCP tool.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Display name for the agent"},
                "description": {"type": "string", "description": "What the agent does"},
                "tools": {"type": "string", "description": "Comma-separated tool names (e.g. search_and_read, browse_page, ask_ai)"},
                "system_prompt": {"type": "string", "description": "Jinja2 system prompt body. Variables: {{ task }}, {{ agent_name }}, {{ date }}"},
                "model": {"type": "string", "description": "Optional model override"},
            },
            "required": ["name", "description", "tools", "system_prompt"],
        },
        "handler": lambda args: execute_agent_create(
            args["name"],
            args["description"],
            args["tools"],
            args["system_prompt"],
            args.get("model", ""),
        ),
    },
    "openweb_agent_delete": {
        "description": "Delete an agent template from vault/agents/.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Agent name/slug to delete"},
            },
            "required": ["name"],
        },
        "handler": lambda args: execute_agent_delete(args["name"]),
    },
    "openweb_thinking_log": {
        "description": "Save a reasoning trace to vault/thinking/ for transparency.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the reasoning trace"},
                "reasoning": {"type": "string", "description": "The full reasoning chain"},
                "conclusion": {"type": "string", "description": "Final conclusion (optional)"},
            },
            "required": ["title", "reasoning"],
        },
        "handler": lambda args: execute_thinking_log(
            args["title"],
            args["reasoning"],
            args.get("conclusion", ""),
        ),
    },
    "openweb_update_config": {
        "description": "Update OpenWebUI global web search settings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "web_search": {"type": "string", "description": "Enable web search: 'true' or 'false'"},
                "search_engine": {"type": "string", "description": "Search engine: 'searxng', 'google', etc."},
                "searxng_url": {"type": "string", "description": "SearXNG query URL (e.g. 'http://192.168.0.33:8888/search?q=<query>')"},
            },
        },
        "handler": lambda args: tool_update_config(
            args.get("web_search", ""),
            args.get("search_engine", ""),
            args.get("searxng_url", ""),
        ),
    },
}


def _build_agent_mcp_tools():
    """Dynamically create MCP tools from vault/agents/ templates."""
    tools = {}
    for agent in _get_agent_summaries():
        slug = agent["slug"]
        tools[f"openweb_agent_{slug}"] = {
            "description": f"Delegate a task to the {agent['name']} sub-agent. {agent['description']}.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "The task to delegate to the agent"},
                },
                "required": ["task"],
            },
            "handler": (lambda s: lambda args: execute_agent_execute(s, args["task"]))(slug),
        }
    return tools


# Merge static TOOLS with dynamic agent tools
TOOLS.update(_build_agent_mcp_tools())


def send_message(msg: dict):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    """MCP stdio server."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            send_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "openwebui", "version": "1.0.0"},
                },
            })
        elif method == "notifications/initialized":
            pass  # no response needed
        elif method == "tools/list":
            tools = []
            for name, t in TOOLS.items():
                tools.append({
                    "name": name,
                    "description": t["description"],
                    "inputSchema": t["inputSchema"],
                })
            send_message({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}})
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            tool = TOOLS.get(tool_name)
            if not tool:
                send_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                })
                continue
            try:
                result = tool["handler"](arguments)
                send_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
                })
            except Exception as e:
                send_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                        "isError": True,
                    },
                })
        elif method == "ping":
            send_message({"jsonrpc": "2.0", "id": msg_id, "result": {}})


if __name__ == "__main__":
    main()
