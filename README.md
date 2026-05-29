# Sloth Agent — OpenWebUI Autonomous AI Agent

Autonomous AI agent built on [OpenWebUI](https://github.com/open-webui/open-webui) with 16 custom tools, voice I/O, code artifacts, sub-agents, and an MCP integration layer. Self-hosted, privacy-first.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Rog (192.168.0.52) — Windows 11, CPU workstation     │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Claude Code ← MCP (stdio) ← openwebui_mcp.py │   │
│  │    ↓                                             │   │
│  │  openwebui_mcp.py (2935 lines)                   │   │
│  │    • Tool handlers: bash, files, browser, etc    │   │
│  │    • Jinja2 system prompt renderer               │   │
│  │    • Streaming SSE parser (25-round tool loop)   │   │
│  │    • Artifact/skill/agent MCP tools              │   │
│  └────────────────────┬────────────────────────────┘   │
│                       │ HTTPS                          │
└───────────────────────┼───────────────────────────────┘
                        │
┌───────────────────────┼───────────────────────────────┐
│  Lappy (192.168.0.33) — GPU server, Docker host       │
│  ┌────────────────────┴────────────────────────────┐   │
│  │  Docker: webui-net                               │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │   │
│  │  │open-webui│  │ alphabetty│  │telegram-bridge│  │   │
│  │  │ :8080    │  │ :7700    │  │              │  │   │
│  │  └────┬─────┘  └────┬─────┘  └──────────────┘  │   │
│  │       │              │                          │   │
│  │  ┌────┴──────────┐ ┌┴─────────────────────┐  │   │
│  │  │ litellm :4000  │ │ searxng-vpn :8888     │  │   │
│  │  │ (124+ models)  │ │ (Google/Bing/DDG)     │  │   │
│  │  └───────────────┘ └───────────────────────┘  │   │
│  │                                                 │   │
│  │  Host services:                                 │   │
│  │  • Kokoro TTS :8006                             │   │
│  │  • Whisper STT :8007                            │   │
│  │  • OpenAI Audio Proxy :8005                     │   │
│  │  • Artifact Server :8012                        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## What's Inside

### `openwebui_mcp.py` — Core MCP server
The heart of the project. A stdio MCP server that bridges Claude Code (or any MCP client) to OpenWebUI's API. Provides:

- **Chat** (`openweb_chat`) — Streaming chat with 25-round tool loop. Sends tool_ids, renders system prompt via Jinja2, auto-logs chats to vault.
- **Tool execution** — 11 custom tool handlers (alphabetty, bash, files, browser, vision, knowledge graph, graph visuals, obsidian, voice, artifacts, skills) run on the host via MCP.
- **Artifact tools** (`openweb_create/list/update_artifact`) — Sandboxed code preview on port 8012.
- **Skill tools** (`openweb_skill_list/load/execute`) — Reusable Jinja2 prompt templates from vault.
- **Sub-agent tools** (`openweb_agent_list/load/coder/researcher/writer`) — Template-based delegation.
- **Config** (`openweb_get/update_config`) — Web search, retrieval settings.
- **DISABLED**: `openweb_update_model` — Corrupted model DB. Use DB-direct access instead.

### Templates (`templates/`)
- `system_prompt.j2` — Jinja2 template for sloth-agent's system prompt (tools, vault, methodology, agents)
- `chat_note.j2` — Chat auto-log format with frontmatter
- `chat_history.j2` — Recent chat context injection

### Services (`services/`)
- `openai_audio_proxy.py` — Translates OpenAI `/audio/speech` + `/v1/audio/speech` to Kokoro TTS
- `artifact_server.py` — Sandboxed code preview (HTML/React/SVG/Mermaid/JS/CSS), CSP, CDN whitelist
- `stt_server.py` / `tts_server_kokoro.py` — Whisper STT + Kokoro TTS servers
- `create_subagents.py` — Registers researcher/coder/writer models in OpenWebUI

### Vault (`vault/`)
Obsidian vault for agent notes, chat logs, skills, and agent templates.
- `vault/skills/*.md` — Reusable prompt templates (landing-page, chart, form, email, report, summarize)
- `vault/agents/*.md` — Sub-agent definitions (researcher, coder, writer)
- `vault/chats/{user}/*.md` — Auto-logged conversations with frontmatter
- `vault/thinking/*.md` — Reasoning traces from extended thinking

### Telegram Bridge (`telegram-bridge/`)
Telegram bot that relays messages to sloth-agent via OpenWebUI API. Docker container on `webui-net`.

## Tools on sloth-agent

| # | Tool | Functions | Backend |
|---|------|-----------|----------|
| 1 | alphabetty | deep_research, search_and_read, ask_ai | Alphabetty REST (Tailscale:7700) |
| 2 | bash_tool | execute_bash | subprocess (local) / SSH (lappy) |
| 3 | file_system | read_file, write_file, edit_file, list_directory | Host file I/O |
| 4 | browser_control | browse_page, screenshot, click, type, extract | Alphabetty CDP |
| 5 | vision | analyze_image, generate_image | Alphabetty image API |
| 6 | knowledge_graph | graph_search, graph_stats, entity_graph, list_tags, list_spaces, list_conversations | Alphabetty graph API |
| 7 | graph_visuals | mermaid_diagram, entity_network | Mermaid syntax generation |
| 8 | obsidian | vault_list, vault_read, vault_write, vault_search, vault_recent | Host file I/O (vault/) |
| 9 | voice | speech_to_text, text_to_speech | Whisper STT + Kokoro TTS |
| 10 | artifacts | create_artifact, list_artifacts, update_artifact | Artifact server (port 8012) |
| 11 | skills | skill_list, skill_load, skill_execute | Vault skills (Jinja2 templates) |
| 12-16 | Built-in | memory, git_tools, web_search, url_fetcher, docker_manager | OpenWebUI native |

## Sub-Agents

Template-based agents defined in `vault/agents/*.md`:

| Agent | Base Model | Tools | Purpose |
|-------|-----------|-------|---------|
| researcher | zai-glm-5.1 | web_search, url_fetcher | Multi-source research, fact-checking |
| coder | zai-glm-5.1 | — | Code generation, debugging |
| writer | zai-glm-5.1 | web_search | Prose, copy, reports, documentation |

New agents can be created at runtime with `agent_create` (name, tools, system prompt, optional model override).

## Infrastructure

| Service | Host | Port | Notes |
|---------|------|------|-------|
| OpenWebUI | Lappy (Docker) | 8080→3000 | Web UI + API |
| LiteLLM | Lappy (Docker) | 4000 | 124+ models, proxy to upstream APIs |
| SearXNG | Lappy (Docker, VPN) | 8888 | Google/Bing/DuckDuckGo, `language=en`, limiter on |
| Alphabetty | Lappy (Docker) | 7700 | Research, CDP, images, chat, knowledge graph |
| Kokoro TTS | Lappy (host) | 8006 | ONNX TTS, multiple voices |
| Whisper STT | Lappy (host) | 8007 | CUDA STT, model "base" |
| Audio Proxy | Lappy (host) | 8005 | OpenAI format → Kokoro/Whisper |
| Artifact Server | Lappy (host) | 8012 | Sandboxed code preview |

## OpenWebUI Model Config (sloth-agent)

The model config is stored directly in OpenWebUI's SQLite DB. Correct structure:

```
model.meta  → {profile_image_url, description, tools: [...16 IDs...], capabilities, features}
model.params → {system_prompt: "...", function_calling: "native"}
```

**NEVER put `params` inside `meta`** — this causes LiteLLM BadRequestError.

To modify model config:
```bash
cat << 'PYEOF' | ssh aaron@192.168.0.33 'docker exec -i open-webui python3'
import sqlite3, json
db = sqlite3.connect("/app/backend/data/webui.db")
# Read/modify model rows, then:
db.commit()
PYEOF
ssh aaron@192.168.0.33 'docker restart open-webui'
```

## Setup

1. Clone repo on both Rog and Lappy
2. On Lappy: deploy OpenWebUI, LiteLLM, SearXNG, Alphabetty via Docker
3. On Lappy: start TTS/STT/audio proxy/artifact server via scheduled tasks
4. On Rog: register MCP server via `claude mcp add openwebui -- python openwebui_mcp.py`
5. Access at http://192.168.0.33:3000 (admin: aaron@slothitude.com)

## Known Issues

- **Empty response after tool calls** (#27) — MCP tool loop drops final text chunk. Affects Telegram bridge too.
- **TTS/STT sampling rate** (#28) — Audio proxy sample rate conversion pipeline needs audit.

## Scorecard

| Category | Score |
|----------|-------|
| Autonomy | 8/10 |
| Tool Breadth | 9/10 |
| Memory/RAG | 9/10 |
| Multi-Model | 10/10 |
| Ease of Use | 6/10 |
| Privacy/Self-Host | 10/10 |
| Ecosystem | 5/10 |
| **Total** | **57/70** |
