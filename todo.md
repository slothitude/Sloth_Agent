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
- [x] **STT/TTS servers** — copied from voicebox, deployed to Lappy, running on :8006 (TTS) and :8007 (STT)
- [x] **Voice tool** — registered on OpenWebUI (speech_to_text, text_to_speech, list_voices)
- [x] **Git repo** — pushed to github.com/slothitude/Sloth_Agent, cloned on Lappy
- [x] **HTTPS** — ai.retromonkey.com.au via Oracle Caddy + Tailscale + acme.sh (ZeroSSL cert)
- [x] **OpenAI audio proxy** — port 8005, translates OpenAI format to Kokoro/Whisper

### Tools on sloth-agent (17 registered)
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
14. voice — speech_to_text, text_to_speech, list_voices
15. artifacts — create_artifact, list_artifacts, update_artifact
16. skills — skill_list, skill_load, skill_execute
17. agents — agent_list, agent_load, agent_create, agent_delete, delegate_to (template-based)
18. Agent Vault knowledge base — RAG indexed

### MCP tool_ids sent in requests
["alphabetty", "bash_tool", "file_system", "browser_control", "vision", "knowledge_graph", "graph_visuals", "obsidian", "voice", "artifacts", "skills"]

---

## Phase 3 — Audit Deficiencies (from competitor comparison)

### HIGH Priority
- [x] **#15 Voice I/O** — STT (faster-whisper :8007) + TTS (kokoro-onnx :8006) deployed and running
  - [x] Servers running on Lappy via scheduled tasks
  - [x] OpenWebUI custom tool registered (speech_to_text, text_to_speech, list_voices)
  - [x] MCP-side handlers in openwebui_mcp.py
  - [x] Configure OpenWebUI admin audio settings to point to STT/TTS
  - [x] Test end-to-end voice chat in OpenWebUI UI
- [x] **#16 Artifacts** — sandboxed code preview (HTML/React/SVG/Mermaid/JS/CSS)
  - [x] Artifact server on Lappy port 8012 (services/artifact_server.py)
  - [x] Scheduled task Artifact-Server for persistence
  - [x] OpenWebUI custom tool registered (create_artifact, list_artifacts, update_artifact)
  - [x] MCP-side handlers in openwebui_mcp.py + MCP tools
  - [x] System prompt updated with Artifacts instructions
- [x] **#17 Skills system** — reusable prompt templates loadable on demand
  - [x] Vault-based: `vault/skills/*.md` with Jinja2 rendering
  - [x] 6 starter skills: landing-page, chart, form, email-draft, report, summarize
  - [x] Users can create/share skills by writing .md files to vault/skills/
  - [x] skill_list, skill_load, skill_execute tools registered
  - [x] OpenWebUI custom tool registered + MCP tools
- [x] **#25 Agent system** — template-based sub-agents with dynamic MCP tool generation
  - [x] Vault-based: `vault/agents/*.md` with YAML frontmatter + Jinja2 system prompt
  - [x] 3 starter agents: researcher, coder, writer
  - [x] agent_list, agent_load, agent_create, agent_delete + delegate_to (template-first, AGENT_TOOLS fallback)
  - [x] Dynamic MCP tools: `openweb_agent_{slug}` auto-generated per template
  - [x] OpenWebUI custom tool registered + MCP tools
  - [x] System prompt updated with agent builder docs

### MEDIUM Priority
- [ ] **#18 Computer Use (interactive screen)** — full GUI control beyond headless CDP
  - Alphabetty CDP does headless browser; need VNC/noVNC for desktop control
  - Reference: Claude Computer Use
- [x] **#19 Extended Thinking** — deep reasoning with chain-of-thought logging
  - thinking_log tool saves reasoning traces to vault/thinking/ with frontmatter
  - Available in CUSTOM_TOOL_SCHEMAS + MCP tool (openweb_thinking_log)
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
- [ ] **#24 Moonlight game streaming** — serve games via Moonlight/Sunshine
  - Sunshine host on Lappy (GPU), Moonlight clients on LAN devices
  - Could integrate with sloth-agent for voice-controlled game launch
- [ ] **#26 GodotStrap** — AI-to-Godot UI bridge (`C:\Users\aaron\Documents\godotstrap`)
  - Docker stack: Bridge (Godot 4.6.3 + Xvfb) + Viewer (Python viewport capture) on port 7778
  - Agent emits JSON component tree → Godot renders real Control nodes → interactive stream to browser
  - Input proxy forwards browser clicks back to Godot engine
  - Aero Design System (Glassmorphism, soft shadows, Tailwind palettes)
  - OpenWebUI integration via artifact viewer
  - Ref templates: Dashboard, System Monitor, Wizard

### Security / Ops (from Phase 1)
- [x] **Security: restrict file_system** to safe directories (whitelist) — `FILE_SYSTEM_ROOTS` with path validation on read/write/edit
- [x] **Security: sandbox bash** commands (blocklist dangerous commands) — 16 blocked patterns (rm -rf /, mkfs, format, dd if=, etc.)
- [x] **Performance: cache Alphabetty API key** (already cached in session via `_alphabetty_key`)
- [ ] **Add more Alphabetty tools** (workflows, sign-in automation, macros)
- [ ] **Mount vault folder into Docker** — blocked: vault is on Rog, Docker on Lappy. Would need SMB mount or vault sync service first.
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
