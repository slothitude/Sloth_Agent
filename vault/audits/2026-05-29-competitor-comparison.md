---
created: "2026-05-29"
tags: [audit, comparison, competitors]
type: audit
---

# Competitor Audit: sloth-agent vs Claude Desktop vs OpenClaw vs Goose

> Generated 2026-05-29 — comprehensive feature comparison

## Feature Matrix

| Feature | sloth-agent | Claude Desktop | OpenClaw | Goose |
|---|---|---|---|---|
| **Core LLM** | Any (LiteLLM 124+ models) | Claude only | Any (Ollama, OpenAI, etc.) | Any (multi-provider) |
| **Agent Loop** | 25 rounds, client-side | Built-in, auto | Built-in, auto | Built-in, auto |
| **Web Search** | SearXNG (unlimited) | Perplexity-style | Plugin-based | Plugin-based |
| **Deep Research** | Alphabetty multi-round | Projects + research | Skills | Extensions |
| **File System** | read/write/edit/list | Full local access | Sandboxed workspace | Full local access |
| **Shell/Bash** | Local + SSH (Lappy) | Terminal access | Terminal access | Terminal access |
| **Browser Control** | CDP (navigate, click, type, screenshot) | Computer Use | Browser skill | Browser tool |
| **Vision** | Analyze + Generate images | Analyze only | Plugin | Plugin |
| **Code Editor** | File tools + bash | Inline Artifacts | IDE integration | IDE integration |
| **Memory** | Obsidian vault + RAG | Persistent memory | Knowledge base | Session-based |
| **Knowledge Graph** | Alphabetty graph (full CRUD) | None native | Plugin | Plugin |
| **MCP Support** | Native (tool server) | Native (core feature) | Native (core) | Native (extensions) |
| **RAG** | OpenWebUI built-in + vault | Projects docs | Knowledge base | Extensions |
| **Multi-User** | Yes (isolated chats, shared vault) | Single user | Multi-tenant | Single user |
| **Chat Logging** | Auto to Obsidian per-user | Session history | Platform-dependent | Session history |
| **Templates** | Jinja2 (prompts, notes, history) | Skills | Skills | Config-based |
| **Planning** | System prompt methodology | Extended Thinking | Skill-based | Configurable |
| **Graph Viz** | Mermaid diagrams | None native | Plugin | Plugin |
| **Platforms** | Web (OpenWebUI) | Desktop app | 13+ platforms | Desktop + CLI |
| **Voice** | No | Yes | Yes (via platforms) | No |
| **Artifacts** | No | Yes (live preview) | No | No |
| **Computer Use** | CDP (headless) | Full screen control | Plugin | No |
| **Skill/Plugin Market** | No | Skills gallery | 3000+ community skills | Extension registry |
| **Collaboration** | Multi-user shared vault | No | Multi-channel teams | No |
| **Self-Hosted** | Yes (full control) | No | Yes | Yes |
| **Open Source** | Partial (OpenWebUI + custom) | No | Yes | Yes |
| **SSH/Remote** | Yes (Lappy, Pi, Oracle) | No native | Plugin | No |
| **Docker** | Built-in manager | No | Plugin | No |
| **Git** | Built-in tool | No native | Plugin | Plugin |

## Gaps — What sloth-agent Needs

| Priority | Gap | How to Fix |
|---|---|---|
| **HIGH** | Artifacts (live code preview) | OpenWebUI code blocks already render; add iframe sandbox for HTML/React |
| **HIGH** | Voice I/O | Add Whisper + TTS tool (Lappy has TTS on :8006) |
| **HIGH** | Skill marketplace / reusable prompts | Vault-based skills folder + Jinja2 templates loadable on demand |
| **MEDIUM** | Computer Use (full screen control) | Alphabetty CDP already does headless; add VNC/noVNC for interactive |
| **MEDIUM** | Extended Thinking (deep reasoning) | System prompt already plans; add chain-of-thought logging to vault |
| **MEDIUM** | Multi-platform (Discord, Slack, Telegram) | OpenWebUI has webhook support; or n8n workflows as bridges |
| **LOW** | Plugin marketplace | Community tools can be registered as OpenWebUI custom tools |
| **LOW** | Mobile app | OpenWebUI is already responsive PWA |

## Unique Features (sloth-agent only)

| Unique Feature | Why It Matters |
|---|---|
| **Knowledge Graph** (Alphabetty) | Persistent entity/relationship memory across sessions |
| **Mermaid Diagrams** | Native graph visualization without external tools |
| **Multi-User Shared Vault** | Collaborative memory with isolated chat histories |
| **Jinja2 Templates** | Dynamic system prompts with live context injection |
| **SSH/Remote Execution** | Run commands on any machine in the LAN |
| **Docker Manager** | Built-in container control |
| **Self-hosted + Any LLM** | Full control, no vendor lock-in, unlimited models |
| **Deep Research Pipeline** | Multi-round research with source extraction |

## Score Card

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

## Verdict

sloth-agent leads in tool breadth, memory/RAG, multi-model support, and privacy. Main gaps: voice, artifacts, skill marketplace, and multi-platform reach. The vault + Jinja2 + knowledge graph combo is unique — no competitor has all three.

Next priorities:
1. Voice I/O (Whisper + TTS)
2. Artifacts (iframe sandbox)
3. Skills system (vault-based reusable prompts)
4. Multi-platform bridges (n8n + webhooks)
