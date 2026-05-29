# OpenWeb Claude Desktop - Todo

## Goal: Make OpenWebUI sloth-agent behave like Claude Desktop / Goose AI / OpenClaw

### Completed
- [x] Streaming chat with agent tool loop (openwebui_mcp.py) — 25 rounds
- [x] Web search via SearXNG (search_web)
- [x] URL fetching (fetch_url)
- [x] Deep research via Alphabetty (deep_research, search_and_read)
- [x] Ask AI / consult other models via Alphabetty (ask_ai)
- [x] Knowledge base, notes, tasks, automations (OpenWebUI built-in)
- [x] Memory, git, docker tools registered on sloth-agent
- [x] **#5 Full bash tool** — execute_bash (local + SSH to Lappy)
- [x] **#6 File system** — read_file, write_file, edit_file, list_directory
- [x] **#7 Agent loop** — increased to 25 rounds
- [x] **#3 Browser control** — browse_page, screenshot, click_element, type_text, extract_data (via Alphabetty CDP)
- [x] **#2 Vision** — analyze_image, generate_image (via Alphabetty)
- [x] **#4 MCP server integration** — Alphabetty added as native MCP tool server in OpenWebUI
- [x] **#1 Code editor** — covered by file_system + bash_tool combo (same as Claude Desktop)
- [x] **#10 System prompt** — autonomous planning, tool awareness, OpenWebUI-as-brain
- [x] **#8 Knowledge graph** — graph_search, graph_stats, entity_graph, list_tags, list_spaces, list_conversations
- [x] **#9 Graph visualization** — mermaid_diagram, entity_network
- [x] **#12 Planning/reflection** — system prompt methodology (plan first, iterate, verify)
- [x] **#11 Obsidian vault** — vault at C:/Users/aaron/openweb_claude_desktop/vault/ + OpenWebUI RAG knowledge base
- [x] **Competitor audit** — sloth-agent (57/70) vs OpenClaw (56/70) vs Claude Desktop (41/70) vs Goose (42/70)

### Completed — Phase 2
- [x] **Jinja2 templates** — dynamic system prompts, chat notes, chat history
- [x] **Chat auto-logging** — all chats saved to vault/chats/{user}/ with frontmatter
- [x] **Smart system prompt** — includes recent chat context, session info, user identity
- [x] **Multi-user** — admin account, isolated chats, shared vault
- [x] **STT/TTS servers** — copied from voicebox (services/stt_server.py, services/tts_server_kokoro.py)

### Tools on sloth-agent (14 registered)
1. memory — Memory (built-in)
2. git_tools — Git Tools (built-in)
3. web_search — Web Search (built-in)
4. url_fetcher — URL Fetcher (built-in)
5. docker_manager — Docker Manager (built-in)
6. alphabetty — deep_research, search_and_read, ask_ai
7. bash_tool — execute_bash (local/lappy)
8. file_system — read_file, write_file, edit_file, list_directory
9. browser_control — browse_page, screenshot, click_element, type_text, extract_data
10. vision — analyze_image, generate_image
11. knowledge_graph — graph_search, graph_stats, entity_graph, list_tags, list_spaces, list_conversations
12. graph_visuals — mermaid_diagram, entity_network
13. obsidian — vault_list, vault_read, vault_write, vault_search, vault_recent
14. Agent Vault knowledge base — RAG indexed

### MCP tool_ids sent in requests
["alphabetty", "bash_tool", "file_system", "browser_control", "vision", "knowledge_graph", "graph_visuals", "obsidian"]

---

## Phase 3 — Audit Deficiencies (from competitor comparison)

### HIGH Priority
- [ ] **#15 Voice I/O** — STT (faster-whisper :8007) + TTS (kokoro-onnx :8006) as tools on sloth-agent
  - STT server ready at `services/stt_server.py` — needs deployment to Lappy + tool registration
  - TTS server ready at `services/tts_server_kokoro.py` — already running on Lappy :8006
  - Need: OpenWebUI custom tool or MCP-side handler to proxy audio in/out
  - Need: Frontend microphone button (OpenWebUI built-in supports this)
- [ ] **#16 Artifacts** — live code preview (HTML/React/SVG iframe sandbox)
  - OpenWebUI code blocks already render; need iframe sandbox for executable output
  - Reference: Claude Desktop Artifacts pattern
- [ ] **#17 Skills system** — reusable prompt templates loadable on demand
  - Vault-based: `vault/skills/*.md` with Jinja2 rendering
  - Users can create/share skills via vault
  - Need: skill_list, skill_load, skill_execute tools

### MEDIUM Priority
- [ ] **#18 Computer Use (interactive screen)** — full GUI control beyond headless CDP
  - Alphabetty CDP does headless browser; need VNC/noVNC for desktop control
  - Reference: Claude Computer Use
- [ ] **#19 Extended Thinking** — deep reasoning with chain-of-thought logging
  - System prompt already plans; add CoT logging to vault for transparency
  - Need: thinking_log tool that saves reasoning traces
- [ ] **#20 Multi-platform bridges** — Discord, Slack, Telegram, etc.
  - OpenWebUI has webhook support; n8n workflows as bridges
  - OpenClaw has 13+ platforms — we need at least Telegram bridge
- [ ] **#21 Streaming audio** — real-time TTS streaming (chunked response)
  - Current TTS generates full WAV then returns; need chunked streaming for low latency
  - WebSocket or SSE audio stream

### LOW Priority
- [ ] **#22 Plugin marketplace** — community tool registry
  - OpenWebUI custom tools can be registered dynamically
  - Need: tool registry + install workflow
- [ ] **#23 Mobile app** — OpenWebUI is already responsive PWA
  - May just need PWA manifest + service worker tweaks
  - Voice I/O on mobile = killer feature

### Security / Ops (from Phase 1)
- [ ] **Security: restrict file_system** to safe directories (whitelist)
- [ ] **Security: sandbox bash** commands (blocklist dangerous commands)
- [ ] **Performance: cache Alphabetty API key** (already cached in session)
- [ ] **Add more Alphabetty tools** (workflows, sign-in automation, macros)
- [ ] **Mount vault folder into Docker** for direct OpenWebUI tool access
- [ ] **Auto-sync vault to OpenWebUI RAG** knowledge base

### Audit Score Card (2026-05-29)
| Category | sloth-agent | Claude Desktop | OpenClaw | Goose |
|---|---|---|---|---|
| Autonomy | 8/10 | 7/10 | 8/10 | 7/10 |
| Tool Breadth | 9/10 | 7/10 | 9/10 | 6/10 |
| Memory/RAG | 9/10 | 6/10 | 7/10 | 5/10 |
| Multi-Model | 10/10 | 1/10 | 9/10 | 9/10 |
| Ease of Use | 6/10 | 9/10 | 8/10 | 7/10 |
| Privacy/Self-Host | 10/10 | 3/10 | 8/10 | 8/10 |
| Ecosystem | 5/10 | 6/10 | 10/10 | 5/10 |
| **Total** | **57/70** | **41/70** | **56/70** | **42/70** |
