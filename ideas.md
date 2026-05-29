# OpenWeb Claude Desktop — Brainstorm

## Vision
Build a self-hosted, Goose-like AI agent desktop that wraps OpenWebUI with full agent capabilities: bash terminal, file management, tool calling, and extensible plugins. Think "Claude Code in a browser" or "Goose AI Desktop but self-hosted."

---

## Key Inspirations

### Goose AI Desktop (Block/AI Alliance)
- **Extension-based architecture** — tools are add-ons that connect apps and workflows
- **Subagents** — spawn child agents for delegated tasks, automatic lifecycle management
- **Desktop + CLI + API** — three surfaces, same engine
- **MCP integration** — native Model Context Protocol for extensibility
- **Recipes** — saved prompt templates that chain multiple tool calls
- **Interactive UI in chat** — extensions render buttons, forms, visualizations
- Open source, Apache 2.0, ~45k GitHub stars

### OpenWebUI + Open Terminal
- **Open Terminal** (ghcr.io/open-webui/open-terminal) — lightweight REST API terminal
  - Docker sandboxed or bare metal
  - File browser, command execution, code running
  - Integrates natively into Open WebUI sidebar
  - API key auth, multi-user isolation
- **Native function calling** — models invoke terminal tools directly
- **Tool execution system** — 4 pathways: built-in, Python functions, external tool servers, OpenAPI
- Already has: chat UI, model management, RAG, multi-user, workspace

### OpenCode
- Go-based TUI coding agent, 95k+ stars
- Client/server architecture (model behind API, agent runs locally)
- 75+ LLM providers, MCP support
- Subagent spawning, slash commands, session management

---

## Architecture Options

### Option A: OpenWebUI + Open Terminal (Extend Existing)
**Stack:** OpenWebUI + Open Terminal + custom plugins

How:
1. Deploy OpenWebUI on Lappy (already at port 3000)
2. Deploy Open Terminal container alongside it
3. Write custom OpenWebUI tools/plugins for:
   - File read/write/search (beyond what Open Terminal gives)
   - Web search (SearXNG integration)
   - Code analysis (LSP-style grep/ast)
   - Git operations
4. Configure native function calling on your models (Qwen3.5, etc.)
5. Add MCP tool servers for extensible tooling

Pros:
- Fastest to get running — OpenWebUI is already deployed
- Battle-tested UI, multi-user, auth built in
- Open Terminal gives bash + file management out of the box
- Plugin ecosystem exists

Cons:
- Constrained by OpenWebUI's architecture
- Plugin security is a concern (CVE-2026-0766 — exec() without sandboxing)
- UI customization limited
- Not a true desktop app — browser-based

### Option B: Custom Agent Shell (New Build)
**Stack:** Electron/Tauri + React/Next.js + Python backend

How:
1. Build a desktop shell (Tauri for Rust, or Electron)
2. Frontend: chat UI with tool output panels (terminal, file tree, code editor)
3. Backend: Python FastAPI agent loop
   - LLM client (Ollama/LiteLLM for multi-provider)
   - Tool execution engine (bash, file ops, web)
   - MCP client for extensions
4. Session management, workspaces, project context

Pros:
- Full control over UX — can match Goose/Claude Code feel
- Native file system access
- No browser sandbox limitations
- Can integrate with existing Alphabetty/infrastructure

Cons:
- Significant development effort
- Need to build auth, multi-user, model management from scratch

### Option C: Hybrid — OpenWebUI Backend + Custom Frontend
**Stack:** OpenWebUI API + custom React/Next.js frontend

How:
1. Use OpenWebUI as the backend (model management, auth, chat API)
2. Build a custom React frontend that adds:
   - Split-pane layout: chat | terminal | file tree | code editor
   - Tool call visualization (like Claude Code shows bash output)
   - MCP tool browser
   - Workspace/project management
3. Connect to Open Terminal for bash execution
4. Add SearXNG, file tools, git tools as custom plugins

Pros:
- Best of both worlds — proven backend + custom UX
- Can incrementally add features
- Reuses OpenWebUI's model management and auth
- Can deploy as PWA or Electron wrapper

Cons:
- Still need to build the frontend
- May fight OpenWebUI's API limitations

---

## Recommended Stack (Option C — Hybrid)

### Backend
- **OpenWebUI** (already on Lappy:3000) — model hub, auth, chat completions
- **Open Terminal** (ghcr.io/open-webui/open-terminal) — bash, file ops, code execution
- **LiteLLM Proxy** (already on Lappy:4000) — multi-provider LLM routing
- **Ollama** (already on Lappy:11434) — local models
- **SearXNG** (already on Lappy:8888) — web search
- **Custom MCP servers** — for extra tools (git, file analysis, etc.)

### Frontend (New Build)
- **React + TypeScript** with Vite
- **Layout**: Resizable split panes
  - Left: file tree / project browser
  - Center: chat (with inline tool output)
  - Right: terminal (xterm.js) + code editor (Monaco)
  - Bottom: tool call log
- **State**: Zustand or Jotai
- **Styling**: Tailwind CSS
- **Terminal**: xterm.js (real PTY over WebSocket)
- **Code editor**: Monaco Editor (VS Code engine)
- **Deploy**: Docker + serve as PWA, or Electron/Tauri wrapper for native

### Key Features
1. **Agent Chat** — send messages, get responses with tool calls
2. **Bash Tool** — execute commands, see output in real-time
3. **File Tools** — read, write, search, edit files
4. **Code Editor** — open files from agent output, edit with syntax highlighting
5. **Web Search** — integrated SearXNG results in chat
6. **MCP Browser** — list and enable/disable tool servers
7. **Workspaces** — project-based sessions with context
8. **Tool Permissions** — approve/deny tool calls (like Claude Code)
9. **History** — conversation history with tool call replay
10. **Multi-model** — switch between local (Ollama) and cloud models

---

## Plugin/Extension Ideas

### Core Tools (MCP Servers)
| Tool | Description | Status |
|------|-------------|--------|
| bash | Execute shell commands | Open Terminal |
| files | Read/write/search/edit files | Open Terminal |
| search | Web search via SearXNG | Custom MCP |
| grep | Code search (ripgrep) | Custom MCP |
| git | Git operations (status, diff, commit) | Custom MCP |
| browser | Navigate/extract web pages | Alphabetty CDP |
| memory | Persistent notes/preferences | Mnemosyne MCP |
| calendar | Task scheduling | Custom |
| docker | Container management | Custom MCP |

### Integration Plugins
- **Alphabetty** — search, browse, deep research, knowledge graph
- **Mnemosyne** — memory, deliberations, research briefs
- **Context7** — library documentation lookup
- **n8n** — workflow automation
- **VLC** — media playback
- **Plotter** — pen plotter control (for fun)

### Claude Code Compatibility
- Could build a Claude Code-like skill system
- Slash commands mapped to plugin actions
- CLAUDE.md support for project context
- Hook system for pre/post tool execution

---

## Quick Start Path

### Phase 1: Get Open Terminal Running (1 day)
```bash
# On Lappy
docker run -d --name open-terminal --restart unless-stopped \
  -p 8001:8000 \
  -v open-terminal:/home/user \
  -e OPEN_TERMINAL_API_KEY=your-secret-key \
  ghcr.io/open-webui/open-terminal
```
Connect to existing OpenWebUI at Lappy:3000

### Phase 2: Custom React Frontend (1-2 weeks)
- Scaffold Vite + React + TypeScript + Tailwind
- Build split-pane layout
- Connect to OpenWebUI API for chat
- Connect to Open Terminal WebSocket for terminal
- Add file browser, code editor

### Phase 3: Tool Plugins (ongoing)
- Write MCP servers for search, git, grep
- Add tool permission system
- Build tool call visualization

### Phase 4: Polish (ongoing)
- Workspace management
- Multi-session
- Keyboard shortcuts
- Theme system
- Electron/Tauri wrapper for native feel

---

## Open Questions
- Desktop app framework: Electron vs Tauri vs just PWA?
- Auth: use OpenWebUI's or build custom?
- State sync: how to share context between chat and tools?
- Security: sandbox model for bash execution (Docker vs nsjail vs Firecracker)?
- Model: which local model for best tool calling? Qwen3.5 32B? Or cloud only?

---

## References
- [Open Terminal GitHub](https://github.com/open-webui/open-terminal) — 2.6k stars, MIT
- [Goose Docs](https://goose-docs.ai/) — extension/subagent architecture
- [OpenCode](https://opencode.ai/) — 95k stars, Go TUI agent
- [OpenWebUI Tools Docs](https://docs.openwebui.com/features/extensibility/plugin/tools/)
- [Open Terminal Setup](https://docs.openwebui.com/features/open-terminal/setup/connecting/)
- [OpenClaude](https://github.com/Gitlawb/openclaude) — open Claude Code clone, Ollama + MCP
