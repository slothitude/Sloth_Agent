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
ALPHABETTY_BASE = "http://localhost:7700"
ALPHABETTY_BOOTSTRAP = "alphabetty-bootstrap-secret"
_alphabetty_key = None

# Jinja2 template engine
HERE = os.path.dirname(os.path.abspath(__file__))
VAULT_ROOT = os.path.join(HERE, "vault")
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(HERE, "templates")),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
_current_user = "aaron"  # default user for vault logging

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


def execute_read_file(path):
    """Read a file and return its contents."""
    try:
        p = path.replace("\\", "/")
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
        p = path.replace("\\", "/")
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
        p = path.replace("\\", "/")
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


# --- Chat logging to vault ---


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
        return template.render(
            model=MODEL,
            user=_current_user,
            session_date=time.strftime("%Y-%m-%d %H:%M"),
            recent_chats=recent,
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
        "tool_ids": ["alphabetty", "bash_tool", "file_system", "browser_control", "vision", "knowledge_graph", "graph_visuals", "obsidian", "voice"],
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
    """Update an OpenWebUI model by fetching current config, merging changes, delete+recreate."""
    token = get_token()

    # Get current model config
    models_data = api("GET", "/api/models", token)
    if "error" in models_data:
        return models_data
    current = None
    for m in models_data.get("data", []):
        if m.get("id") == model_id:
            current = m
            break
    if not current:
        return {"error": f"Model '{model_id}' not found"}

    info = current.get("info", {}) or {}
    meta = dict(info.get("meta", {}) or {})

    # Merge capabilities
    caps = dict(meta.get("capabilities") or {})
    if capabilities:
        for pair in capabilities.split(","):
            k, v = pair.strip().split("=", 1)
            caps[k.strip()] = v.strip().lower() == "true"
    meta["capabilities"] = caps

    # Merge features
    feats = dict(meta.get("features") or {})
    if web_search:
        feats["web_search"] = web_search.lower() == "true"
    if feats:
        meta["features"] = feats

    # Merge params
    params = dict(meta.get("params") or {})
    if function_calling:
        params["function_calling"] = function_calling
    if params:
        meta["params"] = params

    # Merge tools list
    if tools:
        meta["tools"] = [t.strip() for t in tools.split(",")]

    # Delete old model (via GET filter + internal API)
    # OpenWebUI doesn't have a clean delete endpoint for created models
    # We need to hit the internal models table directly
    del_result = api("GET", f"/api/v1/models/{model_id}/delete", token)
    # If that fails, try brute force: recreate won't work if exists

    # Try to recreate with merged config
    create_body = {
        "id": model_id,
        "name": info.get("name", model_id),
        "base_model_id": info.get("base_model_id", ""),
        "meta": meta,
        "params": meta.get("params", {}),
    }
    # Remove params from meta to avoid duplication (it's a top-level field too)
    if "params" in meta:
        create_body["params"] = meta["params"]

    result = api("POST", "/api/v1/models/create", token, create_body)

    if "error" in result and "already registered" in result["error"]:
        return {
            "error": f"Model '{model_id}' already exists. OpenWebUI doesn't support model deletion via API. "
                     f"Delete it manually in the UI at http://192.168.0.33:3000/workspace/models then retry. "
                     f"The merged config that would be applied: {json.dumps(meta, indent=2)[:500]}"
        }

    return {"updated": True, "model_id": model_id, "meta": meta, "api_response": result}


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
