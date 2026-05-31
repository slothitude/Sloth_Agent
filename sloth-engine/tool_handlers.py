"""Sloth Engine — tool handlers.

All execute_* functions. Each takes keyword args and returns a string result.
"""

from __future__ import annotations

import base64
import json
import os
import ipaddress
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from threading import Lock

import jinja2

from config import (
    ALLOWED_ROOTS, ARTIFACT_BASE, AUDIO_BASE, BASH_DANGEROUS_PATTERNS,
    SEARXNG_URL, STT_BASE, VAULT_DIR,
)
from godotstrap_client import (
    gs_health, gs_state, gs_events, gs_screenshot, gs_reset,
    gs_render, gs_write_scene, gs_open_scene, GODOTSTRAP_VIEWER_URL,
)

_HERE = Path(__file__).parent
_VAULT_ROOT = str(VAULT_DIR)
_session_key: str | None = None
_session_key_time: float = 0
_SESSION_KEY_TTL = 1800  # 30 minutes

# Jinja2 envs (sandboxed to prevent SSTI)
_skills_env = jinja2.sandbox.SandboxedEnvironment(
    loader=jinja2.FileSystemLoader(str(VAULT_DIR / "skills")),
    autoescape=False, trim_blocks=True, lstrip_blocks=True,
)
_agents_env = jinja2.sandbox.SandboxedEnvironment(
    loader=jinja2.FileSystemLoader(str(VAULT_DIR / "agents")),
    autoescape=False, trim_blocks=True, lstrip_blocks=True,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _fs_safe(path: str) -> tuple[bool, str]:
    """Check if a path is within allowed roots. Uses realpath to prevent symlink traversal."""
    try:
        p = os.path.realpath(path)
    except (OSError, ValueError):
        return False, path
    for root in ALLOWED_ROOTS:
        try:
            r = os.path.realpath(root)
        except (OSError, ValueError):
            continue
        # Path must start with root + separator (or be exactly root)
        if p == r or p.startswith(r + os.sep):
            return True, p
    return False, p


def _vault_safe(path: str) -> str | None:
    try:
        full = os.path.realpath(os.path.join(_VAULT_ROOT, path.lstrip("/")))
        root = os.path.realpath(_VAULT_ROOT)
    except (OSError, ValueError):
        return None
    if not full.startswith(root + os.sep) and full != root:
        return None
    return full


def _parse_frontmatter(text: str) -> tuple[dict, str]:
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


def _get_session_key_sync() -> str:
    """Get or acquire Alphabetty session key (sync, using urllib). Refreshes after TTL."""
    global _session_key, _session_key_time
    if _session_key and (time.time() - _session_key_time) < _SESSION_KEY_TTL:
        return _session_key
    from config import ALPHABETTY_BOOTSTRAP, ALPHABETTY_BASE
    req = urllib.request.Request(
        f"{ALPHABETTY_BASE}/api/auth/session/acquire",
        data=json.dumps({}).encode(),
        headers={"X-Bootstrap-Token": ALPHABETTY_BOOTSTRAP, "Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read().decode())
    _session_key = data.get("api_key") or data.get("key") or data.get("session_key") or data.get("token")
    if not _session_key:
        for v in data.values():
            if isinstance(v, str) and len(v) > 20:
                _session_key = v
                break
    if not _session_key:
        raise RuntimeError(f"Cannot extract session key from Alphabetty: {data}")
    _session_key_time = time.time()
    return _session_key


def _alphabetty_request_sync(method: str, path: str, body=None, params=None, timeout=120, raw=False):
    """Sync Alphabetty request using urllib (safe inside async event loop)."""
    from config import ALPHABETTY_BASE
    key = _get_session_key_sync()
    url = f"{ALPHABETTY_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        if raw:
            return resp.read()
        ct = resp.headers.get("Content-Type", "")
        if "image" in ct:
            return resp.read()  # raw bytes
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()[:500]}"}


def _alphabetty_sse_sync(path: str, body: dict) -> str:
    """Sync SSE consume using urllib — blocks until stream completes."""
    from config import ALPHABETTY_BASE
    key = _get_session_key_sync()
    url = f"{ALPHABETTY_BASE}{path}"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=300)
        tokens = []
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace")
            if not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if event.get("type") == "token":
                tokens.append(event.get("content", ""))
            elif event.get("type") == "done":
                break
            elif event.get("type") == "error":
                return event.get("content", "Unknown SSE error")
        return "".join(tokens) or '{"status": "completed"}'
    except Exception as e:
        return f"SSE error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Search & Research
# ═══════════════════════════════════════════════════════════════════════════

def execute_search_web(query: str) -> str:
    url = f"{SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json"
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        results = []
        for r in data.get("results", [])[:5]:
            results.append(f"- **{r.get('title', '')}**\n  URL: {r.get('url', '')}\n  {r.get('content', '')}")
        return "\n\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {e}"


_PRIVATE_PREFIXES = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("0.0.0.0/8"),
)


def _is_safe_url(url: str) -> bool:
    """Block SSRF: reject private/internal IPs and non-HTTP schemes."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    # Block localhost variants
    if hostname in ("localhost", "localhost.localdomain") or hostname.endswith(".local"):
        return False
    try:
        addrs = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        for family, _, _, _, sockaddr in addrs:
            ip = ipaddress.ip_address(sockaddr[0])
            for network in _PRIVATE_PREFIXES:
                if ip in network:
                    return False
    except socket.gaierror:
        return False
    return True


def execute_fetch_url(url: str) -> str:
    if not _is_safe_url(url):
        return "Error: URL blocked (private/internal address or invalid scheme)"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000] if text else "Empty page."
    except Exception as e:
        return f"Fetch error: {e}"


def execute_read_url(url: str, format: str = "markdown") -> str:
    params = {"url": url}
    if format:
        params["format"] = format
    return str(_alphabetty_request_sync("GET", "/api/read-url", params=params))[:5000]


def execute_deep_research(query: str, depth: int = 3, mode: str = "detailed") -> str:
    return _alphabetty_sse_sync("/api/research", {"query": query, "depth": depth, "mode": mode})


def execute_search_and_read(query: str, max_results: int = 3) -> str:
    return str(_alphabetty_request_sync("POST", "/api/search-and-read", {
        "query": query, "max_results": max_results,
    }))[:5000]


def execute_ask_ai(query: str, mode: str = "concise", search_enabled: bool = True) -> str:
    return _alphabetty_sse_sync("/api/chat", {"query": query, "mode": mode, "search_enabled": search_enabled})


# ═══════════════════════════════════════════════════════════════════════════
# Bash
# ═══════════════════════════════════════════════════════════════════════════

def execute_bash(command: str, host: str = "local") -> str:
    for pat in BASH_DANGEROUS_PATTERNS:
        if re.search(pat, command, re.IGNORECASE):
            return f"Error: Command blocked (matched dangerous pattern)"
    timeout = 120
    try:
        if host == "lappy":
            proc = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=5",
                 "aaron@192.168.0.33", command],
                capture_output=True, text=True, timeout=timeout,
            )
        else:
            proc = subprocess.run(["bash", "-c", command], capture_output=True, text=True, timeout=timeout)
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
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# File System
# ═══════════════════════════════════════════════════════════════════════════

def execute_read_file(path: str) -> str:
    try:
        safe, p = _fs_safe(path)
        if not safe:
            return f"Error: Path '{path}' is outside allowed directories."
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read()[:10000] or "(empty file)"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except IsADirectoryError:
        return f"Error: Path is a directory: {path}"
    except Exception as e:
        return f"Error: {e}"


def execute_write_file(path: str, content: str) -> str:
    try:
        safe, p = _fs_safe(path)
        if not safe:
            return f"Error: Path '{path}' is outside allowed directories."
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Error: {e}"


def execute_edit_file(path: str, old_text: str, new_text: str) -> str:
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


def execute_list_directory(path: str = "") -> str:
    if not path:
        return "Error: path is required (no default directory listing)"
    try:
        safe, p = _fs_safe(path)
        if not safe:
            return f"Error: Path '{path}' is outside allowed directories."
        entries = []
        for entry in sorted(os.listdir(p)):
            full = os.path.join(p, entry)
            if os.path.isdir(full):
                entries.append(f"  {entry}/")
            else:
                entries.append(f"  {entry} ({os.path.getsize(full)} bytes)")
        return "\n".join(entries) if entries else "(empty directory)"
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Browser (Alphabetty CDP)
# ═══════════════════════════════════════════════════════════════════════════

def execute_browse_page(url: str) -> str:
    try:
        _alphabetty_request_sync("POST", "/api/cdp/navigate", {"url": url})
        result = _alphabetty_request_sync("GET", "/api/cdp/content")
        return str(result.get("content", ""))[:8000] if isinstance(result, dict) else str(result)[:8000]
    except Exception as e:
        return f"Browse error: {e}"


def execute_screenshot(format: str = "png") -> str:
    try:
        result = _alphabetty_request_sync("GET", f"/api/cdp/screenshot?format={format}")
        # Result is raw image bytes (not JSON) when successful
        if isinstance(result, bytes):
            import hashlib
            fname = f"{time.strftime('%Y%m%d-%H%M%S')}-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}.png"
            img_dir = _HERE / "data" / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            fpath = img_dir / fname
            with open(fpath, "wb") as f:
                f.write(result)
            return json.dumps({"status": "success", "url": f"/api/images/{fname}", "size": len(result)})
        return json.dumps(result)[:500]
    except Exception as e:
        return f"Screenshot error: {e}"


def execute_click_element(selector: str) -> str:
    try:
        result = _alphabetty_request_sync("POST", "/api/cdp/click", {"selector": selector})
        return str(result)[:500]
    except Exception as e:
        return f"Click error: {e}"


def execute_type_text(selector: str, text: str) -> str:
    try:
        result = _alphabetty_request_sync("POST", "/api/cdp/type", {"selector": selector, "text": text})
        return str(result)[:500]
    except Exception as e:
        return f"Type error: {e}"


def execute_extract_data(expression: str) -> str:
    try:
        result = _alphabetty_request_sync("POST", "/api/cdp/extract", {"expression": expression})
        return str(result)[:3000]
    except Exception as e:
        return f"Extract error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Vision
# ═══════════════════════════════════════════════════════════════════════════

def execute_analyze_image(image_source: str, prompt: str = "Describe this image in detail") -> str:
    try:
        body = {"query": prompt}
        if image_source.startswith("http"):
            body["url"] = image_source
        else:
            body["file_path"] = image_source
        result = _alphabetty_request_sync("POST", "/api/files/analyze", body)
        return str(result)[:5000]
    except Exception as e:
        return f"Image analysis error: {e}"


def execute_generate_image(prompt: str, width: int = 1024, height: int = 1024) -> str:
    try:
        result = _alphabetty_request_sync("POST", "/api/images/generate", {
            "prompt": prompt, "width": width, "height": height,
        }, timeout=120)
        if isinstance(result, dict) and result.get("status") == "success":
            # Save image to disk and return a URL
            import hashlib
            img_data = result.get("image", "")
            slug = hashlib.sha256(prompt.encode()).hexdigest()[:12]
            fname = f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}.png"
            img_dir = _HERE / "data" / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            fpath = img_dir / fname
            # Extract base64 from data URI
            if "," in img_data:
                img_data = img_data.split(",", 1)[1]
            with open(fpath, "wb") as f:
                f.write(base64.b64decode(img_data))
            return json.dumps({"status": "success", "url": f"/api/images/{fname}", "prompt": prompt, "size": fpath.stat().st_size})
        return str(result)[:2000]
    except Exception as e:
        return f"Image generation error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Knowledge Graph
# ═══════════════════════════════════════════════════════════════════════════

def execute_graph_search(query: str, limit: int = 10) -> str:
    try:
        result = _alphabetty_request_sync("GET", f"/api/graph/search?query={urllib.parse.quote(query)}&limit={limit}")
        return str(result)[:5000]
    except Exception as e:
        return f"Graph search error: {e}"


def execute_graph_stats() -> str:
    try:
        result = _alphabetty_request_sync("GET", "/api/graph/stats")
        return str(result)[:3000]
    except Exception as e:
        return f"Graph stats error: {e}"


def execute_entity_graph(entity_name: str, depth: int = 2) -> str:
    try:
        result = _alphabetty_request_sync("GET", f"/api/graph/entity/{urllib.parse.quote(entity_name)}?depth={depth}")
        return str(result)[:5000]
    except Exception as e:
        return f"Entity graph error: {e}"


def execute_list_tags() -> str:
    try:
        result = _alphabetty_request_sync("GET", "/api/graph/tags")
        return str(result)[:3000]
    except Exception as e:
        return f"List tags error: {e}"


def execute_list_spaces() -> str:
    try:
        result = _alphabetty_request_sync("GET", "/api/spaces")
        return str(result)[:3000]
    except Exception as e:
        return f"List spaces error: {e}"


def execute_list_conversations() -> str:
    try:
        result = _alphabetty_request_sync("GET", "/api/conversations")
        return str(result)[:5000]
    except Exception as e:
        return f"List conversations error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Vault (Obsidian)
# ═══════════════════════════════════════════════════════════════════════════

def execute_vault_list(path: str = "") -> str:
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


def execute_vault_read(path: str) -> str:
    target = _vault_safe(path)
    if not target:
        return "Error: Path outside vault"
    if not os.path.isfile(target):
        return f"Error: Not found: {path}"
    with open(target, "r", encoding="utf-8", errors="replace") as f:
        return f.read()[:10000] or "(empty)"


def execute_vault_write(path: str, content: str) -> str:
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


def execute_vault_search(query: str, max_results: int = 10) -> str:
    results = []
    ql = query.lower()
    for root, dirs, files in os.walk(os.path.normpath(_VAULT_ROOT)):
        dirs[:] = [d for d in dirs if d != ".obsidian"]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, _VAULT_ROOT).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                if ql in text.lower():
                    idx = text.lower().index(ql)
                    ctx = text[max(0, idx - 60):idx + len(ql) + 60].replace("\n", " ").strip()
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


# ═══════════════════════════════════════════════════════════════════════════
# Artifacts (local file-based, no external server needed)
# ═══════════════════════════════════════════════════════════════════════════

_ARTIFACT_DIR = _HERE / "data" / "artifacts"
_ARTIFACT_INDEX = _ARTIFACT_DIR / "index.json"
_artifact_lock = Lock()


def _load_artifact_index() -> dict:
    with _artifact_lock:
        if _ARTIFACT_INDEX.exists():
            try:
                return json.loads(_ARTIFACT_INDEX.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}


def _save_artifact_index(idx: dict):
    with _artifact_lock:
        _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        _ARTIFACT_INDEX.write_text(json.dumps(idx, indent=2), encoding="utf-8")


def execute_create_artifact(title: str, source: str, type: str = "html") -> str:
    try:
        _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-").strip("-")[:60] or "untitled"
        ts = time.strftime("%Y%m%d-%H%M%S")
        ext_map = {"html": "html", "svg": "svg", "javascript": "js", "python": "py",
                    "mermaid": "html", "code": "txt", "css": "css", "react": "html"}
        ext = ext_map.get(type, "html")
        fname = f"{ts}-{slug}.{ext}"
        fpath = _ARTIFACT_DIR / fname
        fpath.write_text(source, encoding="utf-8")
        aid = fpath.stem
        # Update index
        idx = _load_artifact_index()
        idx[aid] = {"id": aid, "title": title, "type": type, "file": fname,
                     "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "size": fpath.stat().st_size}
        _save_artifact_index(idx)
        return json.dumps({"status": "ok", "id": aid, "url": f"/api/artifacts/{fname}", "title": title, "type": type})
    except Exception as e:
        return json.dumps({"error": str(e)})


def execute_list_artifacts() -> str:
    try:
        idx = _load_artifact_index()
        if not idx:
            _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
            files = list(_ARTIFACT_DIR.glob("*")) if _ARTIFACT_DIR.exists() else []
            return json.dumps([{"id": f.stem, "title": f.stem, "file": f.name} for f in files if f.name != "index.json"])
        return json.dumps(list(idx.values()))
    except Exception as e:
        return json.dumps({"error": str(e)})


def execute_update_artifact(id: str, source: str) -> str:
    try:
        idx = _load_artifact_index()
        if id not in idx:
            return json.dumps({"error": f"Artifact '{id}' not found"})
        fname = idx[id]["file"]
        fpath = _ARTIFACT_DIR / fname
        fpath.write_text(source, encoding="utf-8")
        idx[id]["size"] = fpath.stat().st_size
        idx[id]["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_artifact_index(idx)
        return json.dumps({"status": "ok", "id": id, "url": f"/api/artifacts/{fname}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
# Voice
# ═══════════════════════════════════════════════════════════════════════════

def execute_speech_to_text(audio_base64: str, language: str = None) -> str:
    try:
        body = json.dumps({"audio": audio_base64, "language": language}).encode()
        req = urllib.request.Request(
            f"{STT_BASE}/v1/audio/transcriptions/json", data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        return json.dumps(data)
    except Exception as e:
        return f"STT error: {e}"


def execute_text_to_speech(text: str, voice: str = "af_bella", speed: float = 1.0) -> str:
    try:
        body = json.dumps({"text": text, "voice": voice, "speed": speed}).encode()
        req = urllib.request.Request(
            f"{AUDIO_BASE}/tts", data=body, headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=60)
        wav_bytes = resp.read()
        audio_b64 = base64.b64encode(wav_bytes).decode()
        return json.dumps({
            "audio_base64": audio_b64,
            "audio_size_bytes": len(wav_bytes),
            "status": "ok",
        })
    except Exception as e:
        return f"TTS error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Skills
# ═══════════════════════════════════════════════════════════════════════════

def execute_skill_list() -> str:
    skills_dir = VAULT_DIR / "skills"
    if not skills_dir.is_dir():
        return "No skills directory found."
    entries = []
    for fname in sorted(skills_dir.iterdir()):
        if not fname.suffix == ".md":
            continue
        try:
            text = fname.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(text)
            name = meta.get("name", fname.stem)
            desc = meta.get("description", "(no description)")
            entries.append(f"- **{fname.stem}** — {desc}")
        except Exception:
            entries.append(f"- **{fname.stem}** — (error reading)")
    return f"Available skills ({len(entries)}):\n\n" + "\n".join(entries) if entries else "No skills found."


def execute_skill_load(name: str) -> str:
    fname = name if name.endswith(".md") else f"{name}.md"
    fpath = VAULT_DIR / "skills" / fname
    if not fpath.is_file():
        return f"Error: Skill '{name}' not found."
    text = fpath.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    result = f"## Skill: {meta.get('name', name)}\n"
    if meta.get("description"):
        result += f"**Description**: {meta['description']}\n"
    result += f"\n---\n\n{body}"
    return result


def execute_skill_execute(name: str, variables: str = "") -> str:
    fname = name if name.endswith(".md") else f"{name}.md"
    fpath = VAULT_DIR / "skills" / fname
    if not fpath.is_file():
        return f"Error: Skill '{name}' not found."
    text = fpath.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    # Parse variables
    var_dict = {}
    if variables:
        if isinstance(variables, str):
            try:
                var_dict = json.loads(variables)
            except json.JSONDecodeError:
                for pair in variables.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        var_dict[k.strip()] = v.strip()
    try:
        template = _skills_env.from_string(body)
        rendered = template.render(**var_dict)
    except jinja2.TemplateError as e:
        return f"Error rendering skill '{name}': {e}"
    return json.dumps({"skill": meta.get("name", name), "prompt": rendered})


# ═══════════════════════════════════════════════════════════════════════════
# Sub-Agents
# ═══════════════════════════════════════════════════════════════════════════

def _get_agent_summaries() -> list[dict]:
    agents_dir = VAULT_DIR / "agents"
    summaries = []
    if not agents_dir.is_dir():
        return summaries
    for fname in sorted(agents_dir.iterdir()):
        if not fname.suffix == ".md":
            continue
        try:
            text = fname.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(text)
            summaries.append({
                "slug": fname.stem,
                "name": meta.get("name", fname.stem),
                "description": meta.get("description", ""),
                "tools": [t.strip() for t in meta.get("tools", "").split(",") if t.strip()],
                "model": meta.get("model", ""),
            })
        except Exception:
            continue
    return summaries


def execute_agent_list() -> str:
    summaries = _get_agent_summaries()
    if not summaries:
        return "No agents found. Add .md files to vault/agents/"
    entries = []
    for a in summaries:
        model_str = f" [{a['model']}]" if a["model"] else ""
        tools_str = ", ".join(a["tools"]) if a["tools"] else "(no tools)"
        entries.append(f"- **{a['slug']}** — {a['description']}{model_str}\n  Tools: {tools_str}")
    return f"Available agents ({len(summaries)}):\n\n" + "\n\n".join(entries)


def execute_agent_load(name: str) -> str:
    fname = name if name.endswith(".md") else f"{name}.md"
    fpath = VAULT_DIR / "agents" / fname
    if not fpath.is_file():
        return f"Error: Agent '{name}' not found."
    text = fpath.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    result = f"## Agent: {meta.get('name', name)}\n"
    result += f"**Tools**: {', '.join(tools) if tools else '(none)'}\n"
    if meta.get("model"):
        result += f"**Model**: {meta['model']}\n"
    result += f"\n---\n\n{body}"
    return result


def execute_delegate_to(agent_id: str, message: str) -> str:
    """Delegate to a sub-agent. Loads template, renders prompt, calls Z.ai API."""
    fname = agent_id if agent_id.endswith(".md") else f"{agent_id}.md"
    fpath = VAULT_DIR / "agents" / fname
    if not fpath.is_file():
        return f"Error: Agent '{agent_id}' not found."
    text = fpath.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    model_override = meta.get("model", "")

    try:
        template = _agents_env.from_string(body)
        system_prompt = template.render(
            task=message, agent_name=meta.get("name", agent_id),
            date=time.strftime("%Y-%m-%d"),
        )
    except jinja2.TemplateError as e:
        system_prompt = body or f"You are a {agent_id} sub-agent."

    # Import here to avoid circular
    from zai_client import chat_with_tools
    from tools import get_schemas_for_tools
    import asyncio

    agent_schemas = get_schemas_for_tools(tools) if tools else []
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    async def _run():
        content = ""
        async for event in chat_with_tools(messages, agent_schemas, model=model_override):
            if event["type"] == "token":
                content += event["content"]
        return content

    try:
        # Check if there's already a running loop (e.g. inside FastAPI)
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = pool.submit(asyncio.run, _run()).result(timeout=120)
    except RuntimeError:
        # No running loop — safe to use asyncio.run
        result = asyncio.run(_run())
    return result[:8000] if result else f"Agent '{agent_id}' returned empty."


# ═══════════════════════════════════════════════════════════════════════════
# Workflows (n8n)
# ═══════════════════════════════════════════════════════════════════════════

def execute_workflow_create(name: str, nodes: str = "[]", connections: str = "{}", active: bool = False) -> str:
    return str(_alphabetty_request_sync("POST", "/api/workflows", {
        "name": name, "nodes": json.loads(nodes), "connections": json.loads(connections), "active": active,
    }))


def execute_workflow_list() -> str:
    return str(_alphabetty_request_sync("GET", "/api/workflows"))


def execute_workflow_run(workflow_id: str, data: str = "{}") -> str:
    return str(_alphabetty_request_sync("POST", f"/api/workflows/{workflow_id}/run", json.loads(data)))


def execute_workflow_status(workflow_id: str, limit: int = 10) -> str:
    return str(_alphabetty_request_sync("GET", f"/api/workflows/{workflow_id}/status?limit={limit}"))


def execute_workflow_delete(workflow_id: str) -> str:
    return str(_alphabetty_request_sync("DELETE", f"/api/workflows/{workflow_id}"))


# ═══════════════════════════════════════════════════════════════════════════
# Sign-in
# ═══════════════════════════════════════════════════════════════════════════

def execute_signin_start(url: str, username: str, password: str) -> str:
    return str(_alphabetty_request_sync("POST", "/api/signin/start", {
        "url": url, "username": username, "password": password,
    }))

def execute_signin_auto(name: str) -> str:
    return str(_alphabetty_request_sync("POST", "/api/signin/auto", {"name": name}))

def execute_signin_status() -> str:
    return str(_alphabetty_request_sync("GET", "/api/signin/status"))

def execute_signin_submit_2fa(code: str) -> str:
    return str(_alphabetty_request_sync("POST", "/api/signin/submit_2fa", {"code": code}))

def execute_signin_check_2fa() -> str:
    return str(_alphabetty_request_sync("GET", "/api/signin/check_2fa"))

def execute_signin_save(name: str, url: str, username: str, password: str,
                         totp_secret: str = "", selectors: str = "") -> str:
    body = {"name": name, "url": url, "username": username, "password": password}
    if totp_secret:
        body["totp_secret"] = totp_secret
    if selectors:
        body["selectors"] = selectors
    return str(_alphabetty_request_sync("POST", "/api/signin/save", body))


# ═══════════════════════════════════════════════════════════════════════════
# Macros
# ═══════════════════════════════════════════════════════════════════════════

def execute_macro_record_start(name: str, url: str = "") -> str:
    return str(_alphabetty_request_sync("POST", "/api/macros/record/start", {"name": name, "url": url}))

def execute_macro_record_stop() -> str:
    return str(_alphabetty_request_sync("POST", "/api/macros/record/stop"))

def execute_macro_play(macro_id: int) -> str:
    return str(_alphabetty_request_sync("POST", "/api/macros/play", {"macro_id": macro_id}))

def execute_macro_list() -> str:
    return str(_alphabetty_request_sync("GET", "/api/macros"))


# ═══════════════════════════════════════════════════════════════════════════
# Video
# ═══════════════════════════════════════════════════════════════════════════

def execute_youtube_play(query: str) -> str:
    """Play a YouTube video on Lappy Chrome via Alphabetty. Falls back to search."""
    try:
        result = _alphabetty_request_sync("POST", "/api/youtube/play", {"query": query})
        if isinstance(result, dict) and result.get("error"):
            raise Exception(result["error"])
        return json.dumps(result) if isinstance(result, dict) else str(result)
    except Exception:
        # Alphabetty endpoint not available — search via SearXNG and return embed URL
        from config import SEARXNG_URL
        try:
            search_url = f"{SEARXNG_URL}/search"
            params = urllib.parse.urlencode({"query": f"youtube {query}", "format": "json", "categories": "videos"})
            req = urllib.request.Request(f"{search_url}?{params}")
            resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
            for r in resp.get("results", []):
                url = r.get("url", "")
                m = re.search(r'(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', url)
                if m:
                    return json.dumps({"status": "ok", "embed_url": f"https://www.youtube.com/embed/{m.group(1)}", "title": r.get("title", query)})
            return json.dumps({"status": "not_found", "error": f"No YouTube video found for: {query}"})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

def execute_play_video(url: str) -> str:
    """Play a video URL on Lappy Chrome via Alphabetty."""
    return json.dumps(_alphabetty_request_sync("POST", "/api/play/video", {"url": url}))


def execute_youtube_embed(query: str) -> str:
    """Search YouTube and return an embeddable iframe URL. Uses SearXNG to find the video."""
    try:
        # Use SearXNG to search YouTube
        from config import SEARXNG_URL
        search_url = f"{SEARXNG_URL}/search"
        params = urllib.parse.urlencode({"query": f"youtube {query}", "format": "json", "categories": "videos"})
        req = urllib.request.Request(f"{search_url}?{params}")
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
        results = resp.get("results", [])

        # Find first YouTube result and extract video ID
        for r in results:
            url = r.get("url", "")
            m = re.search(r'(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', url)
            if m:
                embed_url = f"https://www.youtube.com/embed/{m.group(1)}"
                title = r.get("title", query)
                return json.dumps({"status": "ok", "embed_url": embed_url, "type": "youtube", "query": title})

        # No YouTube result found
        return json.dumps({"status": "not_found", "error": f"No YouTube video found for: {query}"})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


def execute_video_embed(url: str) -> str:
    """Return a video URL embeddable in iframe or video tag."""
    try:
        # If it's a YouTube URL, convert to embed
        if "youtube.com" in url or "youtu.be" in url:
            m = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
            if m:
                return json.dumps({"status": "ok", "embed_url": f"https://www.youtube.com/embed/{m.group(1)}", "type": "youtube", "url": url})
        # Direct video URL — just pass it through for HTML5 video tag
        return json.dumps({"status": "ok", "embed_url": url, "type": "video", "url": url})
    except Exception as e:
        return f"Video embed error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Files & Downloads
# ═══════════════════════════════════════════════════════════════════════════

def execute_upload_file(file_path: str, query: str = "") -> str:
    safe, p = _fs_safe(file_path)
    if not safe:
        return f"Error: Path '{file_path}' is outside allowed directories."
    if not os.path.isfile(p):
        return f"Error: File not found: {file_path}"
    with open(p, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    body = {"filename": os.path.basename(p), "data": data}
    if query:
        body["query"] = query
    return str(_alphabetty_request_sync("POST", "/api/files/upload", body, timeout=30))


def execute_download_save(url: str, filename: str = "", subdir: str = "") -> str:
    return str(_alphabetty_request_sync("POST", "/api/downloads/save", {
        "url": url, "filename": filename, "subdir": subdir,
    }))


def execute_download_list(subdir: str = "") -> str:
    path = f"/api/downloads/list"
    if subdir:
        path += f"?subdir={subdir}"
    return str(_alphabetty_request_sync("GET", path))


# ═══════════════════════════════════════════════════════════════════════════
# Media Stack (Radarr, Sonarr, qBittorrent, Jellyfin, Jellyseerr)
# Calls media-api on Lappy (port 8070) which wraps the MCP tools
# ═══════════════════════════════════════════════════════════════════════════

def _media_tool_call(tool_name: str, args: dict) -> dict:
    """Call a media-stack MCP tool via the media-api on Lappy."""
    from config import MEDIA_API_BASE
    try:
        body = json.dumps({
            "function": {"name": tool_name, "arguments": json.dumps(args)},
            "id": "1",
        }).encode()
        req = urllib.request.Request(
            f"{MEDIA_API_BASE}/v1/tool-call",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        return data.get("result", data)
    except Exception as e:
        return {"error": f"Media stack error: {e}"}


def execute_media_search(query: str) -> str:
    """Search Jellyfin library for movies/TV shows. Returns direct-play stream links."""
    result = _media_tool_call("media_search", {"query": query})
    return json.dumps(result)[:5000]


def execute_search_tmdb(query: str, media_type: str = "movie") -> str:
    """Search TMDb via Jellyseerr for movies or TV shows to request."""
    return json.dumps(_media_tool_call("search_tmdb", {"query": query, "media_type": media_type}))[:3000]


def execute_media_request(media_id: int, media_type: str = "movie") -> str:
    """Request a movie or TV show via Jellyseerr."""
    return json.dumps(_media_tool_call("media_request", {"media_id": media_id, "media_type": media_type}))


def execute_media_requests(status: str = "") -> str:
    """List Jellyseerr requests."""
    args = {}
    if status:
        args["status"] = status
    return json.dumps(_media_tool_call("media_requests", args))[:5000]


def execute_radarr_movies(status: str = "") -> str:
    """List movies in Radarr library."""
    args = {}
    if status:
        args["status"] = status
    return json.dumps(_media_tool_call("radarr_movies", args))[:5000]


def execute_radarr_queue() -> str:
    """Check Radarr download queue."""
    return json.dumps(_media_tool_call("radarr_queue", {}))[:3000]


def execute_sonarr_series(status: str = "") -> str:
    """List series in Sonarr library."""
    args = {}
    if status:
        args["status"] = status
    return json.dumps(_media_tool_call("sonarr_series", args))[:5000]


def execute_sonarr_queue() -> str:
    """Check Sonarr download queue."""
    return json.dumps(_media_tool_call("sonarr_queue", {}))[:3000]


def execute_torrents_list(filter_status: str = "") -> str:
    """List torrents from qBittorrent with status/progress/speed."""
    args = {}
    if filter_status:
        args["filter_status"] = filter_status
    return json.dumps(_media_tool_call("torrents_list", args))[:5000]


def execute_torrents_action(hash: str, action: str = "pause") -> str:
    """Manage a torrent: pause, resume, delete, delete_files, or bump."""
    return json.dumps(_media_tool_call("torrents_action", {"hash": hash, "action": action}))


def execute_media_stack_status() -> str:
    """Show all media containers + VPN + disk space."""
    return json.dumps(_media_tool_call("stack_status", {}))[:3000]


def execute_vpn_status() -> str:
    """Check Gluetun VPN connection (IP, location)."""
    return json.dumps(_media_tool_call("vpn_status", {}))


# ═══════════════════════════════════════════════════════════════════════════
# Thinking
# ═══════════════════════════════════════════════════════════════════════════

def execute_thinking_log(title: str, reasoning: str, conclusion: str = "") -> str:
    thinking_dir = VAULT_DIR / "thinking"
    thinking_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    date = time.strftime("%Y-%m-%d")
    slug = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-").strip("-")[:50] or "trace"
    fname = f"{date}-{slug}.md"
    fpath = thinking_dir / fname
    counter = 1
    while fpath.exists():
        fpath = thinking_dir / f"{date}-{slug}-{counter}.md"
        counter += 1
    note = f"---\ncreated: {ts}\ntags: [thinking, reasoning]\ntitle: {title}\n---\n\n# {title}\n\n{reasoning}\n"
    if conclusion:
        note += f"\n## Conclusion\n{conclusion}\n"
    fpath.write_text(note, encoding="utf-8")
    return f"Thinking trace saved to vault/thinking/{fpath.name}"


# ═══════════════════════════════════════════════════════════════════════════
# GodotStrap
# ═══════════════════════════════════════════════════════════════════════════

async def execute_render_component(component_tree: dict) -> str:
    import asyncio
    viewer_url = await gs_render(component_tree)
    return f"[GODOT_ARTIFACT]{viewer_url}[/GODOT_ARTIFACT]"


async def execute_gs_health() -> str:
    result = await gs_health()
    return json.dumps(result)


async def execute_gs_state() -> str:
    result = await gs_state()
    return json.dumps(result)


async def execute_gs_events(since: float = None) -> str:
    result = await gs_events(since)
    return json.dumps(result)


async def execute_gs_screenshot() -> str:
    data = await gs_screenshot()
    b64 = base64.b64encode(data).decode()
    return json.dumps({"screenshot_base64": b64, "size": len(data)})


async def execute_gs_reset() -> str:
    result = await gs_reset()
    return json.dumps(result)


async def execute_write_scene(tscn_content: str, path: str = "/tmp/scene.tscn") -> str:
    result = await gs_write_scene(tscn_content, path)
    return json.dumps(result)


async def execute_open_scene(path: str) -> str:
    result = await gs_open_scene(path)
    return json.dumps(result)


# ═══════════════════════════════════════════════════════════════════════════
# Agentic Build Methodology
# ═══════════════════════════════════════════════════════════════════════════

def execute_plan_create(project_id: int, plan_name: str, steps: str,
                        build_cmd: str = "", test_cmd: str = "", lint_cmd: str = "",
                        repo_root: str = "", language: str = "", framework: str = "") -> str:
    """Create a plan from a JSON array of steps."""
    import chat_store
    try:
        step_list = json.loads(steps)
        if not isinstance(step_list, list) or not step_list:
            return "Error: steps must be a non-empty JSON array of {title, description}"
    except (json.JSONDecodeError, TypeError) as e:
        return f"Error: invalid steps JSON: {e}"

    # Validate project exists
    proj = chat_store.get_project(project_id)
    if not proj:
        return f"Error: Project {project_id} not found"

    result = chat_store.create_plan(
        project_id, plan_name, step_list,
        build_cmd=build_cmd, test_cmd=test_cmd, lint_cmd=lint_cmd,
        repo_root=repo_root, language=language, framework=framework,
    )
    return json.dumps({"status": "created", "plan_name": plan_name, "total_steps": result["total_steps"],
                      "message": f"Plan '{plan_name}' created with {result['total_steps']} steps. First step is now active. Use todo_next to begin."})


def execute_todo_next(project_id: int) -> str:
    """Get the current active step, or summary if all done."""
    import chat_store
    step = chat_store.get_active_step(project_id)
    if not step:
        summary = chat_store.get_plan_summary(project_id)
        if summary.get("plan") is None:
            return json.dumps({"status": "no_plan", "message": "No active plan for this project. Use plan_create to start."})
        return json.dumps({
            "status": "complete",
            "message": "All steps complete",
            "summary": {
                "plan_name": summary["plan_name"],
                "total": summary["total"],
                "done": summary["done"],
                "failed": summary["failed"],
            },
            "steps": summary["steps"],
        })
    return json.dumps({"status": "active", **step})


def execute_todo_complete(project_id: int, result: str = "") -> str:
    """Mark active step done, advance to next."""
    import chat_store
    completed = chat_store.get_active_step(project_id)
    if not completed:
        return json.dumps({"status": "no_active", "message": "No active step to complete"})
    next_step = chat_store.complete_step(project_id, result=result)
    if next_step:
        return json.dumps({
            "status": "next",
            "completed": completed["title"],
            "next_step": next_step,
            "message": f"Step '{completed['title']}' completed. Next: '{next_step['title']}'",
        })
    return json.dumps({
        "status": "plan_complete",
        "completed": completed["title"],
        "message": f"Step '{completed['title']}' was the last step. Plan complete!",
    })


def execute_todo_fail(project_id: int, error: str = "", retry: bool = True) -> str:
    """Mark active step as failed, optionally retry."""
    import chat_store
    current = chat_store.get_active_step(project_id)
    if not current:
        return json.dumps({"status": "no_active", "message": "No active step to fail"})
    next_step = chat_store.fail_step(project_id, error=error, retry=retry)
    if next_step and next_step.get("id") == current.get("id"):
        # Same step returned — it's a retry
        return json.dumps({
            "status": "retry",
            "step": next_step["title"],
            "retry_count": next_step["retry_count"],
            "error": next_step["error"],
            "message": f"Step '{next_step['title']}' failed (attempt {next_step['retry_count']}/3). Error appended. Try a different approach.",
        })
    if next_step:
        return json.dumps({
            "status": "skipped",
            "failed": current["title"],
            "next_step": next_step,
            "message": f"Step '{current['title']}' failed after max retries. Moving to: '{next_step['title']}'",
        })
    return json.dumps({
        "status": "plan_complete",
        "failed": current["title"],
        "message": f"Step '{current['title']}' was the last step and it failed. Plan complete (with failures).",
    })


def execute_project_context(project_id: int, build_cmd: str = "", test_cmd: str = "",
                             lint_cmd: str = "", repo_root: str = "", language: str = "",
                             framework: str = "") -> str:
    """Set or get project build context."""
    import chat_store
    proj = chat_store.get_project(project_id)
    if not proj:
        return f"Error: Project {project_id} not found"
    # If any args provided, update
    kwargs = {}
    if build_cmd: kwargs["build_cmd"] = build_cmd
    if test_cmd: kwargs["test_cmd"] = test_cmd
    if lint_cmd: kwargs["lint_cmd"] = lint_cmd
    if repo_root: kwargs["repo_root"] = repo_root
    if language: kwargs["language"] = language
    if framework: kwargs["framework"] = framework
    if kwargs:
        return chat_store.set_project_context(project_id, **kwargs)
    # Otherwise return current context
    ctx = chat_store.get_project_context(project_id)
    return json.dumps({"project_id": project_id, "context": ctx or {}})
