# Sloth Engine — Build Checklist

## Phase 1: Core Engine
- [x] config.py — env vars, constants, credentials (Tailscale IP 100.84.161.63)
- [x] models.py — Pydantic request/response models
- [x] auth.py — API key auth, SQLite users, middleware
- [x] chat_store.py — SQLite: projects, conversations, messages
- [x] alphabetty_client.py — Alphabetty bootstrap auth + requests
- [x] godotstrap_client.py — GodotStrap bridge HTTP client
- [x] zai_client.py — Z.ai GLM-5.1 streaming client + tool loop (strips trailing \n)
- [x] tools.py — TOOL_REGISTRY, get_all_schemas(), dispatch_tool()
- [x] tool_handlers.py — all execute_* functions (~75 tools)
- [x] system_prompt.py — static system prompt with GodotStrap section
- [x] engine.py — FastAPI app, routes, SSE streaming, inline image/artifact serving

## Phase 2: Frontend (Mobile-First)
- [x] frontend/index.html — Single-file chat UI (fallback, 913 lines)
  - Dark theme, responsive, touch-friendly, voice input button
  - Image embed (generated-image CSS), artifact iframe embed
  - Thinking block accumulation (single div, hidden by default)
  - SSE streaming with token/tool_calls/image/artifact/done events
- [x] frontend/godot/ — Godot 4.6 Claude Desktop UI clone
  - SSE streaming via JavaScriptBridge (web) / HTTPClient (desktop)
  - Auto-detect API origin via window.location.origin (web) or localhost:3001 (desktop)
  - Conversation history, new chat, typing indicator, dynamic greeting
  - Dark theme, responsive, touch-friendly
- [ ] Godot 4.6 web export as primary UI shell

## Phase 3: Full Feature Parity
- [x] Skills system — vault/skills/*.md Jinja2 templates (6 skills)
- [x] Sub-agents — vault/agents/*.md recursive delegation (3 agents)
- [x] Telegram bridge update instructions — telegram_update.py
- [x] GodotStrap client — render, events, screenshot, scene management
- [x] Chat auto-logging — save to vault/chats/{user}/{date}-{slug}.md after each completion
- [ ] Ollama client (optional) — local model fallback
- [ ] Wire Telegram bridge to new engine (`http://localhost:3001/api/chat`)
- [x] Media-stack MCP integration — Radarr/Sonarr/qBittorrent/VPN/Jellyseerr tools (search, downloads, requests, queue, torrent management)
- [x] YouTube/VLC player integration — YouTube search + play, video URL play, VLC controls (play/pause/seek/volume/playlist)

## Media-Stack Tools (implemented via Alphabetty MCP wrappers)
- [x] media_control — unified search/browse/download/status/pause/resume/bump/restart
- [x] media_search — Jellyfin library search with direct-play links
- [x] media_request — request movie/TV via Jellyseerr (TMDb ID)
- [x] media_requests — list pending/approved requests
- [x] radarr_movies / radarr_queue — list movies and download queue
- [x] sonarr_series / sonarr_queue — list series and download queue
- [x] torrents_list / torrents_action — qBittorrent torrent management
- [x] vpn_status — Gluetun VPN connection check
- [x] stack_status — Docker container health check

## VLC/YouTube Tools (implemented via Alphabetty MCP wrappers)
- [x] youtube_play — search YouTube and navigate to first result
- [x] play_video — play video URL via yt-dlp
- [x] vlc controls — launch, play, pause, stop, next, prev, seek, volume, playlist, loop, shuffle, fullscreen

## Phase 4: Cleanup & Deploy
- [x] requirements.txt
- [x] Copy vault/ to new engine (skills, agents copied)
- [x] .gitignore (data/, __pycache__/, .env, .godot/)
- [x] Deploy to Lappy port 3001 (start.bat with ZAI_API_KEY override)
- [x] Tailscale IP config (100.84.161.63 for all Lappy services)
- [x] Inline artifact server — no external dependency
- [x] Inline image serving — /api/images/ static mount
- [ ] Stop OpenWebUI container (`docker stop open-webui`)
- [ ] Stop LiteLLM container (`docker stop litellm`)
- [ ] Stop Open Terminal container
- [ ] Update Traefik routes — point :3000 → sloth-engine :3001
- [ ] Delete old sloth-agent code from D:/Sloth_Agent/ (keep vault/, audio-stack Docker)

## Mobile UX
- [ ] Toast/notification system — mobile-friendly inline toasts for errors, status updates, tool confirmations

## Bugs Fixed This Session
- [x] `dispatch_tool` not wired to `chat_with_tools()` — "No dispatch function configured"
- [x] `dispatch_fn` returned coroutine — always `await` now
- [x] Alphabetty requests crashed event loop — sync urllib instead of httpx
- [x] ZAI_API_KEY trailing space — `set "VAR=value"` + `.strip()`
- [x] Alphabetty bootstrap 405 — POST with JSON body, `api_key` field
- [x] `read_url` 405 — changed POST→GET with query params
- [x] `screenshot` 405 — changed POST→GET, saves image to file
- [x] Streaming tokens stacked vertically — strip trailing \n from Z.ai tokens
- [x] Thinking blocks per word — accumulate in single div
- [x] `generate_image` returned raw base64 — saves to file, emits image SSE event
- [x] Artifact server connection refused — inline file-based artifacts, no external server
- [x] Path traversal — `_fs_safe()` requires separator
- [x] `_fs_safe` missing from `list_directory` and `upload_file`

## Known Issues
- [ ] `fetch_url` — connection reset on some sites (WinError 10054)
- [x] `delegate_to` — fixed: ThreadPoolExecutor + asyncio.run
- [ ] Lappy system env var `ZAI_API_KEY` has old broken key (start.bat overrides)
- [x] No rate limiting on chat endpoint — fixed: auth rate limiter added
- [ ] No conversation title editing from frontend
- [ ] No PWA manifest.json / service worker
