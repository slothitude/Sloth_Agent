#!/usr/bin/env python3
"""Sandboxed artifact preview server for sloth-agent.

Stores generated code artifacts (HTML, SVG, React, JS, Mermaid, Python, CSS)
and serves them in sandboxed iframes with strict CSP.

Endpoints:
  GET  /health                   — health check
  POST /artifact                  — create artifact (JSON: title, type, source)
  GET  /artifacts                 — list all artifacts (JSON)
  GET  /artifact/<id>             — full preview page with toolbar
  GET  /artifact/<id>/embed      — stripped embeddable iframe version
  GET  /artifact/<id>/raw        — raw source code
  GET  /artifact/<id>/edit        — editor page (textarea + live preview)
  POST /artifact/<id>/update      — update source code
  DELETE /artifact/<id>           — delete artifact
"""

import json
import os
import re
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "D:/Sloth_Agent/artifacts")
PORT = int(os.environ.get("PORT", 8012))
MAX_SIZE = 100 * 1024  # 100KB max artifact size

# CDN sources allowed in CSP
CDN_ORIGINS = (
    "https://unpkg.com",
    "https://cdn.jsdelivr.net",
    "https://esm.sh",
)

# Type wrappers — wrap raw source into a full HTML page for rendering
WRAPPERS = {
    "html": '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>{source}</body></html>',
    "svg": '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh">{source}</body></html>',
    "react": '''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://unpkg.com/react@18/umd/react.development.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js" crossorigin></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head><body><div id="root"></div>
<script type="text/babel">{source}</script>
</body></html>''',
    "javascript": '''<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body>
<script>{source}</script>
</body></html>''',
    "mermaid": '''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>body{{margin:0;display:flex;justify-content:center;}}</style>
</head><body>
<pre class="mermaid">
{source}
</pre>
<script>mermaid.initialize({{startOnLoad:true,theme:'default'}});</script>
</body></html>''',
    "python": '''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body{{margin:1em;background:#1e1e1e;color:#d4d4d4;font-family:'Courier New',monospace;font-size:14px;white-space:pre-wrap;word-wrap:break-word;}}
</style></head><body>{source}</body></html>''',
    "code": '''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body{{margin:1em;background:#1e1e1e;color:#d4d4d4;font-family:'Courier New',monospace;font-size:14px;white-space:pre-wrap;word-wrap:break-word;}}
</style></head><body>{source}</body></html>''',
    "css": '''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{source}</style>
</head><body>
<div class="preview">CSS Preview — add HTML elements to see styling</div>
</body></html>''',
}

# Preview page template
PREVIEW_PAGE = '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title} — Artifact</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;height:100vh;display:flex;flex-direction:column;background:#0f0f0f;color:#e0e0e0}}
.toolbar{{display:flex;align-items:center;gap:8px;padding:8px 12px;background:#1a1a1a;border-bottom:1px solid #333;flex-shrink:0;flex-wrap:wrap}}
.toolbar h1{{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:300px}}
.badge{{padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px}}
.badge-html{{background:#264f78;color:#7db8e0}}
.badge-svg{{background:#785026;color:#e0a84d}}
.badge-react{{background:#264f26;color:#7de07d}}
.badge-javascript{{background:#787826;color:#e0e07d}}
.badge-mermaid{{background:#502678;color:#b07de0}}
.badge-python,.badge-code{{background:#4a4a4a;color:#c0c0c0}}
.badge-css{{background:#78264f;color:#e07db8}}
.btn{{padding:4px 10px;border:1px solid #444;border-radius:4px;background:#2a2a2a;color:#e0e0e0;cursor:pointer;font-size:12px;text-decoration:none}}
.btn:hover{{background:#3a3a3a}}
.spacer{{flex:1}}
.frame{{flex:1;border:none}}
.fullscreen .toolbar{{display:none}}
.fullscreen .frame{{position:fixed;top:0;left:0;width:100%;height:100%;z-index:9999}}
</style></head>
<body>
<div class="toolbar">
  <h1>{escaped_title}</h1>
  <span class="badge badge-{type}">{type}</span>
  <div class="spacer"></div>
  <a class="btn" href="/artifact/{id}/edit" target="_blank">Edit</a>
  <a class="btn" href="/artifact/{id}/raw">Raw</a>
  <button class="btn" onclick="copySource()">Copy</button>
  <button class="btn" onclick="document.body.classList.toggle('fullscreen')">Fullscreen</button>
</div>
<iframe class="frame" sandbox="allow-scripts" src="/artifact/{id}/embed"></iframe>
<script>
function copySource(){{navigator.clipboard.writeText(document.querySelector('textarea#src').value);}}
</script>
<textarea id="src" style="display:none">{escaped_source}</textarea>
</body></html>'''

# Embed page — minimal, just the rendered artifact in iframe
EMBED_PAGE = '<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{{margin:0}}</style></head><body>{rendered}</body></html>'

# Edit page — split pane editor
EDIT_PAGE = '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title} — Edit Artifact</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;height:100vh;display:flex;flex-direction:column;background:#0f0f0f;color:#e0e0e0}}
.toolbar{{display:flex;align-items:center;gap:8px;padding:8px 12px;background:#1a1a1a;border-bottom:1px solid #333}}
.toolbar h1{{font-size:14px;font-weight:600}}
.btn{{padding:4px 10px;border:1px solid #444;border-radius:4px;background:#2a2a2a;color:#e0e0e0;cursor:pointer;font-size:12px}}
.btn:hover{{background:#3a3a3a}}
.container{{flex:1;display:flex;overflow:hidden}}
.editor{{flex:1;background:#1e1e1e;border-right:1px solid #333;display:flex;flex-direction:column}}
.editor textarea{{flex:1;background:#1e1e1e;color:#d4d4d4;border:none;padding:12px;font-family:'Courier New',monospace;font-size:13px;resize:none;tab-size:2}}
.preview{{flex:1;display:flex;flex-direction:column}}
.preview iframe{{flex:1;border:none;background:#fff}}
</style></head>
<body>
<div class="toolbar">
  <h1>{escaped_title} — Edit</h1>
  <button class="btn" onclick="updatePreview()">Update Preview</button>
  <button class="btn" onclick="saveArtifact()">Save</button>
  <a class="btn" href="/artifact/{id}">View</a>
</div>
<div class="container">
  <div class="editor"><textarea id="code" spellcheck="false">{escaped_source}</textarea></div>
  <div class="preview"><iframe id="preview"></iframe></div>
</div>
<script>
let originalSource = document.getElementById('code').value;
function renderForPreview(src, type) {{
    const wrappers = {wrapper_map};
    let html;
    if (type === 'html' || type === 'svg') {{
        html = src;
    }} else {{
        const tpl = wrappers[type] || wrappers['code'];
        html = tpl.replace('\\{source\\}', src);
    }}
    return html;
}}
function updatePreview() {{
    const src = document.getElementById('code').value;
    const html = renderForPreview(src, '{type}');
    const iframe = document.getElementById('preview');
    iframe.srcdoc = html;
}}
function saveArtifact() {{
    const src = document.getElementById('code').value;
    fetch('/artifact/{id}/update', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{source: src}})
    }}).then(r => r.json()).then(d => {{
        if (d.ok) {{ document.title = document.title.replace(' *', ''); originalSource = src; }}
        else {{ alert('Save failed: ' + (d.error || 'unknown')); }}
    }});
}}
// Tab key in textarea
document.getElementById('code').addEventListener('keydown', function(e) {{
    if (e.key === 'Tab') {{
        e.preventDefault();
        const s = this.selectionStart, end = this.selectionEnd;
        this.value = this.value.substring(0,s) + '  ' + this.value.substring(end);
        this.selectionStart = this.selectionEnd = s + 2;
    }}
}});
// Initial preview
updatePreview();
</script>
</body></html>'''


# In-memory store + file backing
_artifacts = {}  # id -> {title, type, source, created, updated}


def _ensure_dir():
    Path(ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)


def _save_meta():
    _ensure_dir()
    meta_path = os.path.join(ARTIFACT_DIR, "_meta.json")
    # Strip source from meta (stored separately)
    meta = {}
    for aid, a in _artifacts.items():
        meta[aid] = {k: v for k, v in a.items() if k != "source"}
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def _save_source(aid, source):
    _ensure_dir()
    with open(os.path.join(ARTIFACT_DIR, f"{aid}.src"), "w", encoding="utf-8") as f:
        f.write(source)


def _load_source(aid):
    path = os.path.join(ARTIFACT_DIR, f"{aid}.src")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _load_all():
    _ensure_dir()
    meta_path = os.path.join(ARTIFACT_DIR, "_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        for aid, m in meta.items():
            m["source"] = _load_source(aid)
            _artifacts[aid] = m


def _wrap_source(source, atype):
    """Wrap source code into a full HTML page based on type."""
    if atype in ("html", "svg"):
        return source
    tpl = WRAPPERS.get(atype, WRAPPERS["code"])
    return tpl.replace("{source}", source)


def _html_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _csp_header(atype):
    """Content-Security-Policy for the artifact type."""
    # Python/code get no script allowance
    if atype in ("python", "code"):
        return "default-src 'none'; style-src 'unsafe-inline'"
    # React/mermaid need CDN scripts
    if atype in ("react", "mermaid"):
        cdn = " ".join(CDN_ORIGINS)
        return f"default-src 'none'; script-src {cdn} 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'"
    # HTML/SVG/JS/CSS — allow inline scripts but no network
    return "default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'"


class ArtifactHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")

        if path == "/health":
            self._json(200, {"status": "ok", "count": len(_artifacts)})

        elif path == "/artifacts":
            self._list_artifacts()

        elif path.startswith("/artifact/"):
            parts = path[len("/artifact/"):].split("/")
            aid = parts[0]
            sub = parts[1] if len(parts) > 1 else ""

            if aid not in _artifacts:
                return self._json(404, {"error": "artifact not found"})

            if sub == "embed":
                self._embed(aid)
            elif sub == "raw":
                self._raw(aid)
            elif sub == "edit":
                self._edit(aid)
            else:
                self._preview(aid)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")

        if path == "/artifact":
            self._create()
        elif path.startswith("/artifact/"):
            parts = path[len("/artifact/"):].split("/")
            aid = parts[0]
            sub = parts[1] if len(parts) > 1 else ""

            if sub == "update":
                self._update(aid)
            else:
                self._json(404, {"error": "not found"})
        else:
            self._json(404, {"error": "not found"})

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        if path.startswith("/artifact/"):
            aid = path[len("/artifact/"):]
            self._delete(aid)
        else:
            self._json(404, {"error": "not found"})

    # --- Handlers ---

    def _create(self):
        body = self._read_json()
        title = body.get("title", "Untitled")
        atype = body.get("type", "html").lower()
        source = body.get("source", "")

        if not source:
            return self._json(400, {"error": "source is required"})
        if len(source.encode("utf-8")) > MAX_SIZE:
            return self._json(400, {"error": f"source exceeds {MAX_SIZE // 1024}KB limit"})
        if atype not in WRAPPERS and atype not in ("html", "svg"):
            return self._json(400, {"error": f"unsupported type: {atype}. Supported: {', '.join(WRAPPERS.keys())}"})

        aid = _make_id()
        now = time.time()
        _artifacts[aid] = {
            "id": aid,
            "title": title,
            "type": atype,
            "source": source,
            "created": now,
            "updated": now,
        }
        _save_source(aid, source)
        _save_meta()

        self._json(201, {"ok": True, "id": aid, "url": f"http://192.168.0.33:{PORT}/artifact/{aid}"})

    def _list_artifacts(self):
        items = []
        for a in sorted(_artifacts.values(), key=lambda x: x["updated"], reverse=True):
            items.append({
                "id": a["id"],
                "title": a["title"],
                "type": a["type"],
                "created": a["created"],
                "updated": a["updated"],
            })
        self._json(200, {"artifacts": items, "count": len(items)})

    def _preview(self, aid):
        a = _artifacts[aid]
        source = _html_escape(a["source"])
        title = _html_escape(a["title"])
        html = PREVIEW_PAGE.format(
            title=title, escaped_title=_html_escape(a["title"]),
            type=a["type"], id=aid, escaped_source=source,
        )
        self._html(200, html)

    def _embed(self, aid):
        a = _artifacts[aid]
        rendered = _wrap_source(a["source"], a["type"])
        html = EMBED_PAGE.format(rendered=rendered)
        csp = _csp_header(a["type"])
        self._html(200, html, extra_headers={"Content-Security-Policy": csp})

    def _raw(self, aid):
        a = _artifacts[aid]
        self.send_response(200)
        content_type = {
            "html": "text/html", "svg": "image/svg+xml", "css": "text/css",
            "javascript": "text/javascript", "python": "text/x-python",
            "react": "text/jsx", "mermaid": "text/plain", "code": "text/plain",
        }.get(a["type"], "text/plain")
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(a["source"].encode("utf-8"))))
        self.end_headers()
        self.wfile.write(a["source"].encode("utf-8"))

    def _edit(self, aid):
        a = _artifacts[aid]
        title = _html_escape(a["title"])
        source = _html_escape(a["source"])
        # Build wrapper map as JS object
        wmap = {}
        for k, v in WRAPPERS.items():
            escaped = v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
            wmap[k] = escaped
        wrapper_js = json.dumps(wmap)
        html = EDIT_PAGE.format(
            title=title, escaped_title=_html_escape(a["title"]),
            type=a["type"], id=aid, escaped_source=source,
            wrapper_map=wrapper_js,
        )
        self._html(200, html)

    def _update(self, aid):
        if aid not in _artifacts:
            return self._json(404, {"error": "artifact not found"})
        body = self._read_json()
        source = body.get("source", "")
        if not source:
            return self._json(400, {"error": "source is required"})
        if len(source.encode("utf-8")) > MAX_SIZE:
            return self._json(400, {"error": f"source exceeds {MAX_SIZE // 1024}KB limit"})
        _artifacts[aid]["source"] = source
        _artifacts[aid]["updated"] = time.time()
        _save_source(aid, source)
        _save_meta()
        self._json(200, {"ok": True, "id": aid})

    def _delete(self, aid):
        if aid not in _artifacts:
            return self._json(404, {"error": "artifact not found"})
        del _artifacts[aid]
        # Remove files
        src_path = os.path.join(ARTIFACT_DIR, f"{aid}.src")
        if os.path.exists(src_path):
            os.remove(src_path)
        _save_meta()
        self._json(200, {"ok": True, "deleted": aid})

    # --- Helpers ---

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        return json.loads(body)

    def _json(self, code, data):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _html(self, code, html, extra_headers=None):
        payload = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        # Quiet logging — only print on error
        if args and hasattr(args[0], '__contains__') and '5' in str(args):
            print(f"[artifact-server] {fmt % args}", flush=True)


def _make_id():
    """Generate a short random ID."""
    import secrets
    return secrets.token_urlsafe(6)[:8]


if __name__ == "__main__":
    _load_all()
    print(f"Artifact server on :{PORT} — artifacts dir: {ARTIFACT_DIR}", flush=True)
    HTTPServer(("0.0.0.0", PORT), ArtifactHandler).serve_forever()
