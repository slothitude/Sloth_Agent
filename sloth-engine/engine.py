"""Sloth Engine — FastAPI application."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Request, Depends, HTTPException, Query
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from config import HOST, PORT, DEBUG, DEFAULT_MODEL, FRONTEND_DIR, DB_PATH, DATA_DIR, VAULT_DIR
from models import ChatRequest, ProjectCreate, TokenRequest, TokenResponse
from auth import init_auth_db, get_current_user, create_user, verify_token
from chat_store import (
    init_db, create_project, list_projects, get_project, delete_project,
    create_conversation, list_conversations, get_conversation, update_conversation_title,
    delete_conversation, add_message, get_messages, get_messages_for_llm,
)
from system_prompt import SYSTEM_PROMPT
from tools import get_all_schemas, dispatch_tool
from zai_client import chat_with_tools

# ── App ────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    init_auth_db()
    init_db()
    # Create default admin user if no users exist
    if _count_users() == 0:
        admin_pw = os.getenv("SLOTH_ADMIN_PASSWORD", "")
        if not admin_pw:
            import secrets
            admin_pw = secrets.token_urlsafe(24)
            print(f"╔══════════════════════════════════════════════════════╗")
            print(f"║  ADMIN TOKEN (save this — not shown again):        ║")
            print(f"║  {admin_pw:<52s}║")
            print(f"╚══════════════════════════════════════════════════════╝")
        try:
            create_user("admin", admin_pw, "Admin")
        except ValueError:
            pass
    yield


app = FastAPI(title="Sloth Engine", version="1.0.0", lifespan=lifespan)

# ── Rate limiting ─────────────────────────────────────────────────────────
_auth_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_AUTH_ATTEMPTS = 10
_AUTH_WINDOW = 300  # seconds

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "frame-src 'self'; connect-src 'self'; media-src 'self' blob:"
    )
    return response


# ── Static Files ────────────────────────────────────────────────────────────


def _count_users() -> int:
    try:
        with sqlite3.connect(DB_PATH) as db:
            return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    except Exception:
        return 0


# ── Static Files ────────────────────────────────────────────────────────────

GODOT_EXPORT_DIR = FRONTEND_DIR / "godot-export"

@app.get("/")
async def serve_frontend():
    """Serve Godot web export or fallback HTML."""
    for d in [GODOT_EXPORT_DIR, FRONTEND_DIR]:
        idx = d / "index.html"
        if idx.exists():
            return FileResponse(idx)
    return {"name": "Sloth Engine", "version": "1.0.0", "status": "running"}

# Static file serving for Godot web export assets.
# Must be added AFTER all API routes to avoid conflicts.
# Starlette Mount doesn't interfere with FastAPI route matching.
from starlette.staticfiles import StaticFiles as _StaticFiles

for _dir in [GODOT_EXPORT_DIR, FRONTEND_DIR]:
    if _dir.is_dir() and (_dir / "index.html").exists():
        app.mount("/static", _StaticFiles(directory=str(_dir), check_dir=True),
                  name="static_files")
        break

# Generated images
_images_dir = DATA_DIR / "images"
_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/images", _StaticFiles(directory=str(_images_dir), check_dir=False),
          name="generated_images")

# Artifacts
_artifacts_dir = DATA_DIR / "artifacts"
_artifacts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/artifacts", _StaticFiles(directory=str(_artifacts_dir), check_dir=False, html=False),
          name="artifacts")


# ── Auth ────────────────────────────────────────────────────────────────────

@app.post("/api/auth/token", response_model=TokenResponse)
async def create_token(req: TokenRequest):
    # Rate limit: max N attempts per window per email
    key = req.email or "anonymous"
    now = time.time()
    _auth_attempts[key] = [t for t in _auth_attempts[key] if now - t < _AUTH_WINDOW]
    if len(_auth_attempts[key]) >= _MAX_AUTH_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many auth attempts. Try again later.")
    _auth_attempts[key].append(now)

    email = verify_token(req.password, req.email)
    if email:
        return TokenResponse(token=req.password, email=email)
    raise HTTPException(status_code=401, detail="Invalid credentials")


# ── Chat Logging ──────────────────────────────────────────────────────────

def _log_chat_to_vault(email: str, title: str, chat_id: int, model: str, tools_used: list[str]):
    """Save conversation log to vault/chats/{user}/{date}-{slug}.md."""
    import re as _re
    try:
        chats_dir = VAULT_DIR / "chats" / email
        chats_dir.mkdir(parents=True, exist_ok=True)

        # Get messages from DB
        messages = get_messages(chat_id)
        if not messages:
            return

        # Build slug from title
        slug = _re.sub(r"[^\w\s-]", "", title.lower()).strip()[:50] or "untitled"
        slug = _re.sub(r"[\s]+", "-", slug).strip("-")

        # Check for existing files with same slug today, add suffix
        today = time.strftime("%Y-%m-%d")
        date_slug = f"{today}-{slug}"
        if (chats_dir / f"{date_slug}.md").exists():
            i = 1
            while (chats_dir / f"{date_slug}-{i}.md").exists():
                i += 1
            date_slug = f"{date_slug}-{i}"

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        msg_count = len(messages)

        # Build markdown
        lines = [
            "---",
            f'created: "{now}"',
            f'updated: "{now}"',
            f"tags: [chat, {email}]",
            f"user: \"{email}\"",
            f'model: "{model}"',
            f"chat_id: \"{chat_id}\"",
            f"tool_calls: {json.dumps(tools_used)}",
            f"message_count: {msg_count}",
            "---",
            "",
            f"# {title}",
            "",
            f"> {email} · {now} · {model}",
            "",
            "## Messages",
            "",
        ]
        for m in messages:
            role = m["role"].capitalize()
            lines.append(f"### {role}")
            lines.append("")
            lines.append(m.get("content", ""))
            lines.append("")

        content = "\n".join(lines)
        (chats_dir / f"{date_slug}.md").write_text(content, encoding="utf-8")
    except Exception:
        pass  # Logging failure should never break chat


# ── Chat (SSE Streaming) ──────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest, user: str = Depends(get_current_user)):
    email = user or req.user_email or "admin"
    model = req.model or DEFAULT_MODEL

    # Get or create conversation
    if req.chat_id:
        conv = get_conversation(req.chat_id)
        if not conv or conv["user_email"] != email:
            raise HTTPException(status_code=404, detail="Conversation not found")
        chat_id = req.chat_id
    else:
        conv = create_conversation(email, req.project_id)
        chat_id = conv["id"]

    # Auto-title from first message
    if not req.chat_id:
        title = req.message[:60].strip() + ("..." if len(req.message) > 60 else "")
        update_conversation_title(chat_id, title)

    # Save user message
    add_message(chat_id, "user", req.message)

    # Build messages for LLM
    history = get_messages_for_llm(chat_id)
    # Build system prompt with project context
    sys_content = SYSTEM_PROMPT
    if req.project_id:
        proj = get_project(req.project_id)
        if proj:
            sys_content += f"\n\n## Current Project\n- Name: {proj['name']}\n- Description: {proj['description']}\n- Working Dir: {proj['working_dir']}\n"

    messages = [{"role": "system", "content": sys_content}]
    messages.extend(history)

    # Get tool schemas
    tool_schemas = get_all_schemas()

    async def event_stream():
        full_content = ""
        tool_names_used = []

        async for event in chat_with_tools(messages, tool_schemas, model, dispatch_fn=dispatch_tool):
            if event["type"] == "token":
                full_content += event["content"]
                yield f"data: {json.dumps({'type': 'token', 'content': event['content']})}\n\n"
            elif event["type"] == "thinking":
                yield f"data: {json.dumps({'type': 'thinking', 'content': event['content']})}\n\n"
            elif event["type"] == "tool_result":
                # Detect image/artifact/video results and emit special events for frontend
                content = event.get("content", "")
                try:
                    payload = content.split("] ", 1)[1] if "] " in content else content
                    # Try JSON parse first, then ast.literal_eval for Python repr
                    try:
                        result_data = json.loads(payload)
                    except (json.JSONDecodeError, IndexError):
                        import ast
                        try:
                            result_data = ast.literal_eval(payload)
                        except (ValueError, SyntaxError):
                            result_data = None

                    def _emit_embed(item):
                        """Emit video/image/artifact SSE event from a result item."""
                        nonlocal full_content
                        if not isinstance(item, dict):
                            return
                        if item.get("url", "").startswith("/api/images/"):
                            yield f"data: {json.dumps({'type': 'image', 'url': item['url'], 'prompt': item.get('prompt', '')})}\n\n"
                            full_content += f"\n![{item.get('prompt', 'image')}]({item['url']})"
                        elif item.get("url", "").startswith("/api/artifacts/"):
                            yield f"data: {json.dumps({'type': 'artifact', 'url': item['url'], 'title': item.get('title', 'Artifact'), 'artifact_type': item.get('type', 'html')})}\n\n"
                            full_content += f"\n[Artifact: {item.get('title', 'view')}]({item['url']})"
                        elif item.get("embed_url"):
                            vtype = item.get("type", "youtube")
                            yield f"data: {json.dumps({'type': 'video', 'embed_url': item['embed_url'], 'video_type': vtype, 'query': item.get('query', '')})}\n\n"
                            full_content += f"\n[Video: {item.get('query', 'video')}]({item['embed_url']})"
                        # media_search: play_lan / play_remote / url with video extensions
                        else:
                            play_url = item.get("play_lan") or item.get("play_remote") or item.get("url", "")
                            if play_url and (".mp4" in play_url or ".mkv" in play_url or ".webm" in play_url or "youtube.com/embed" in play_url):
                                title = item.get("title", item.get("name", "Media"))
                                vtype = "youtube" if "youtube" in play_url else "video"
                                yield f"data: {json.dumps({'type': 'video', 'embed_url': play_url, 'video_type': vtype, 'query': title})}\n\n"
                                full_content += f"\n[Video: {title}]({play_url})"

                    if isinstance(result_data, dict):
                        for chunk in _emit_embed(result_data):
                            yield chunk
                    elif isinstance(result_data, list):
                        for item in result_data:
                            for chunk in _emit_embed(item):
                                yield chunk
                except (json.JSONDecodeError, IndexError):
                    pass
                yield f"data: {json.dumps({'type': 'tool_result', 'content': event['content']})}\n\n"
            elif event["type"] == "tool_calls":
                for tc in event["calls"]:
                    tool_names_used.append(tc["function"]["name"])
                yield f"data: {json.dumps({'type': 'tool_calls', 'calls': event['calls']})}\n\n"
            elif event["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'content': event['content']})}\n\n"

        # Save assistant message with tool usage metadata
        if full_content:
            meta = ""
            if tool_names_used:
                meta = f"\n\n[Tools used: {', '.join(tool_names_used)}]"
            add_message(chat_id, "assistant", full_content + meta)

        # Log chat to vault
        conv = get_conversation(chat_id)
        _log_chat_to_vault(email, conv["title"] if conv else "untitled", chat_id, model, tool_names_used)

        # Signal done
        yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id, 'content': full_content})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Projects ───────────────────────────────────────────────────────────────

@app.get("/api/projects")
async def api_list_projects(user: str = Depends(get_current_user)):
    return list_projects(user)


@app.post("/api/projects")
async def api_create_project(req: ProjectCreate, user: str = Depends(get_current_user)):
    return create_project(user, req.name, req.description, req.working_dir)


@app.get("/api/projects/{project_id}")
async def api_get_project(project_id: int, user: str = Depends(get_current_user)):
    proj = get_project(project_id)
    if not proj or proj["user_email"] != user:
        raise HTTPException(status_code=404, detail="Project not found")
    convs = list_conversations(user, project_id, limit=10)
    return {**proj, "recent_conversations": convs}


@app.delete("/api/projects/{project_id}")
async def api_delete_project(project_id: int, user: str = Depends(get_current_user)):
    if not delete_project(project_id, user):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}


# ── Conversations ──────────────────────────────────────────────────────────

@app.get("/api/chats")
async def api_list_chats(
    project_id: int | None = None,
    user: str = Depends(get_current_user),
):
    return list_conversations(user, project_id)


@app.get("/api/chats/{chat_id}/messages")
async def api_get_messages(chat_id: int, user: str = Depends(get_current_user)):
    conv = get_conversation(chat_id)
    if not conv or conv["user_email"] != user:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return get_messages(chat_id)


@app.delete("/api/chats/{chat_id}")
async def api_delete_chat(chat_id: int, user: str = Depends(get_current_user)):
    if not delete_conversation(chat_id, user):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


# ── Models ──────────────────────────────────────────────────────────────────

@app.get("/api/models")
async def api_models():
    return [
        {"id": "glm-5.1", "name": "GLM-5.1", "provider": "Z.ai", "description": "Primary model"},
    ]


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ── Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("engine:app", host=HOST, port=PORT, reload=DEBUG)
