# OpenWeb Claude Desktop — Option A: Extend OpenWebUI + Open Terminal

## Current State (Already Running on Lappy)

```
Lappy (192.168.0.33)
│
├── OpenWebUI (v0.9.2)          port 3000 → 8080   [HEALTHY]
│   └── Docker: ghcr.io/open-webui/open-webui:main
│   └── Network: open-webui_webui-net (172.22.0.3)
│
├── Open Terminal (v0.9.2)      port 8000           [RUNNING]
│   └── Docker: ghcr.io/open-webui/open-terminal:latest
│   └── Network: open-webui_webui-net (172.22.0.2)
│   └── Has Claude Code CLI installed (via NPM_PACKAGES)
│   └── API Key: a63a2a7ee2d5431d929c776122e3b706.hzHjrJlnfPd7cYfj
│
├── LiteLLM Proxy               port 4000
│   └── Routes to: Ollama (11434), Z.ai, OpenRouter, NVIDIA, MOG
│   └── Master Key: sk-litellm-b15241627ba17201797f1446b25d82a9
│
├── Ollama                       port 11434
│   └── Models: qwen3.5:9b, qwen3:8b, qwen3-fast:4b, qwen2.5-coder:7b, gemma4
│
├── SearXNG                      port 8888
├── n8n                          port 5678
└── Alphabetty                   port 7700
```

**Both containers are on the same Docker network. OpenWebUI can reach Open Terminal at `http://open-terminal:8000`.**

---

## The Plan: 5 Phases to a Full Agent Desktop

### Phase 1: Connect Open Terminal to OpenWebUI (30 minutes)

Open Terminal is already running but may not be wired up in OpenWebUI's settings yet.

**Steps:**
1. Open OpenWebUI at `http://192.168.0.33:3000`
2. Go to Admin Panel → Settings → Integrations → Open Terminal
3. Click "+", fill in:
   - URL: `http://open-terminal:8000` (Docker network name)
   - API Key: `a63a2a7ee2d5431d929c776122e3b706.hzHjrJlnfPd7cYfj`
   - Auth Type: Bearer
4. Save — look for green "Connected" indicator
5. In chat, click the cloud icon (☁) → select the terminal under "System"
6. Test: ask "What OS are you running on?" — agent should execute `uname -a`

**Also enable native function calling on your models:**
1. Workspace → Models → edit your preferred model
2. Under Capabilities → enable "Native Function Calling"
3. This is critical — without it, tool calls use unreliable prompt-based fallback

**Done when:** Agent can run bash commands from OpenWebUI chat.

---

### Phase 2: Configure Models for Tool Calling (1-2 hours)

Not all models handle tools equally. Need to set up which models to use for agent mode.

**Best models for tool calling (available through your setup):**

| Model | Provider | Tool Calling | Notes |
|-------|----------|-------------|-------|
| qwen3.5:32b | Ollama (local) | Good | Best local option if you have VRAM |
| qwen3.5:9b | Ollama (local) | Decent | Currently loaded |
| qwen3:8b | Ollama (local) | Decent | Currently loaded |
| glm-5-turbo | Z.ai (cloud) | Good | Via LiteLLM |
| claude-sonnet-4-20250514 | Z.ai/Anthropic | Excellent | Best tool calling |
| gpt-oss-120b | Z.ai | Good | |
| gemma4 | Ollama (local) | Basic | Not great at tools |

**Steps:**
1. Pull a better model if needed: `ollama pull qwen3.5:32b` (if VRAM allows)
2. In OpenWebUI, create a "Agent" model profile:
   - Workspace → Models → "+"
   - Name it "Agent" or "Code Agent"
   - Set capabilities: Native Function Calling = ON
   - Connect to LiteLLM or Ollama directly
   - System prompt (see Phase 3)
3. Test tool calling with the model

**LiteLLM config additions needed:**
Add these to `/c/docker/litellm/config.yaml` on Lappy if not already there:
```yaml
- model_name: agent-local
  litellm_params:
    model: ollama/qwen3.5
    api_base: http://ollama:11434
    supports_function_calling: true

- model_name: agent-cloud
  litellm_params:
    model: openai/glm-5-turbo
    api_base: https://api.z.ai/api/anthropic
    api_key: a63a2a7ee2d5431d929c776122e3b706.hzHjrJlnfPd7cYfj
    supports_function_calling: true
```

**Done when:** Can switch to a model that reliably invokes terminal tools.

---

### Phase 3: System Prompt + Agent Behavior (1-2 hours)

OpenWebUI lets you set system prompts per model. Write a Claude Code-like system prompt.

**Steps:**
1. In OpenWebUI, Workspace → Models → edit your agent model
2. Set a system prompt. Here's the template:

```
You are an autonomous AI agent with access to a terminal and file system.

You can execute commands, read and write files, search code, and browse the web.
Think step by step. When you need information, run a command. When you need to
change something, edit the file. When you're done, summarize what you did.

## Tools Available
- **Terminal**: Execute any shell command (bash)
- **File Browser**: Read, write, list files
- **Code Execution**: Run Python, Node.js, etc.

## Rules
1. Always read a file before editing it
2. Run tests after making changes
3. Use grep/search to understand code before modifying
4. Explain what you're doing before each tool call
5. If a command fails, read the error and fix it — don't give up
6. Keep responses concise — show output, don't narrate it

## Working Directory
Your working directory is the project you're asked about. Stay inside it.
```

3. Save the model with this prompt
4. Test with: "List all files in the current directory and tell me what project this is"

**Done when:** Agent follows instructions, uses tools proactively.

---

### Phase 4: Custom OpenWebUI Tools (2-3 days)

This is where it gets powerful. OpenWebUI lets you write Python functions as tools that the LLM can invoke. These run server-side.

**Tools to build:**

#### Tool 1: Web Search (SearXNG)
```python
"""
title: Web Search
description: Search the web using SearXNG
author: slothitude
version: 0.1
required_open_webui_version: 0.3.0
"""

import httpx
from pydantic import BaseModel, Field

class Tools:
    def __init__(self):
        self.searxng_url = "http://192.168.0.33:8888"

    async def search_web(self, query: str) -> str:
        """
        Search the web for information.
        Use this when you need current information, documentation, or answers
        that may have changed since your training data.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.searxng_url}/search",
                params={"q": query, "format": "json", "categories": "general"},
                timeout=10
            )
            results = resp.json().get("results", [])[:5]
            output = []
            for r in results:
                output.append(f"- [{r['title']}]({r['url']})\n  {r.get('content', '')}")
            return "\n\n".join(output) if output else "No results found."
```

#### Tool 2: Code Search (Ripgrep)
```python
"""
title: Code Search
description: Search code with ripgrep patterns
author: slothitude
version: 0.1
"""

import subprocess
from pydantic import BaseModel, Field

class Tools:
    def __init__(self):
        pass

    def search_code(self, pattern: str, path: str = "/home/user", file_type: str = "") -> str:
        """
        Search for a pattern in code files.
        Use ripgrep syntax for the pattern.
        """
        cmd = ["rg", "--max-count", "20", "--no-heading", "-n"]
        if file_type:
            cmd.extend(["--type", file_type])
        cmd.extend([pattern, path])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.stdout[:3000] if result.stdout else "No matches found."
        except subprocess.TimeoutExpired:
            return "Search timed out."
```

#### Tool 3: Git Operations
```python
"""
title: Git Tools
description: Git version control operations
author: slothitude
version: 0.1
"""

import subprocess

class Tools:
    def git_status(self, path: str = "/home/user") -> str:
        """Show git status of a repository."""
        result = subprocess.run(
            ["git", "-C", path, "status", "--short"],
            capture_output=True, text=True
        )
        return result.stdout or "Clean working tree."

    def git_diff(self, path: str = "/home/user") -> str:
        """Show unstaged changes."""
        result = subprocess.run(
            ["git", "-C", path, "diff"],
            capture_output=True, text=True
        )
        return result.stdout[:5000] or "No changes."

    def git_log(self, path: str = "/home/user", count: int = 10) -> str:
        """Show recent commit history."""
        result = subprocess.run(
            ["git", "-C", path, "log", f"-{count}", "--oneline"],
            capture_output=True, text=True
        )
        return result.stdout or "No commits."
```

#### Tool 4: Memory/Notes
```python
"""
title: Memory
description: Save and recall information across conversations
author: slothitude
version: 0.1
"""

import json
from pathlib import Path

MEMORY_FILE = Path("/home/user/.agent_memory.json")

class Tools:
    def __init__(self):
        if not MEMORY_FILE.exists():
            MEMORY_FILE.write_text("{}")

    def remember(self, key: str, value: str) -> str:
        """Save a key-value pair for later recall."""
        data = json.loads(MEMORY_FILE.read_text())
        data[key] = value
        MEMORY_FILE.write_text(json.dumps(data, indent=2))
        return f"Remembered: {key}"

    def recall(self, key: str) -> str:
        """Recall a previously saved value."""
        data = json.loads(MEMORY_FILE.read_text())
        return data.get(key, f"Nothing found for '{key}'")

    def list_memories(self) -> str:
        """List all saved memories."""
        data = json.loads(MEMORY_FILE.read_text())
        if not data:
            return "No memories saved."
        return "\n".join(f"- {k}: {v[:100]}" for k, v in data.items())
```

#### Tool 5: URL Fetcher
```python
"""
title: URL Fetcher
description: Fetch and extract text content from a URL
author: slothitude
version: 0.1
"""

import httpx
from pydantic import BaseModel

class Tools:
    async def fetch_url(self, url: str) -> str:
        """
        Fetch a URL and return its text content.
        Good for reading documentation, APIs, articles.
        """
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, timeout=15)
            # Basic HTML to text — for production use readability/trafilatura
            text = resp.text
            # Strip tags crudely (Open Terminal has better options)
            import re
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:10000]
```

#### Tool 6: Docker Manager
```python
"""
title: Docker Manager
description: Manage Docker containers
author: slothitude
version: 0.1
"""

import subprocess

class Tools:
    def docker_ps(self) -> str:
        """List running Docker containers."""
        result = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True
        )
        return result.stdout

    def docker_logs(self, container: str, lines: int = 50) -> str:
        """Get container logs."""
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container],
            capture_output=True, text=True
        )
        return (result.stdout + result.stderr)[-3000:]

    def docker_restart(self, container: str) -> str:
        """Restart a container."""
        result = subprocess.run(
            ["docker", "restart", container],
            capture_output=True, text=True
        )
        return f"Restarted {container}: {result.stdout.strip()}"
```

**How to add tools in OpenWebUI:**
1. Workspace → Tools → "+"
2. Paste the Python code
3. Give it a name and description
4. Enable it for your agent model
5. The LLM will automatically discover and use these tools via function calling

**Done when:** All 6 custom tools are installed and working in chat.

---

### Phase 5: Connect External MCP Servers + Polish (1-2 days)

OpenWebUI supports external tool servers (OpenAPI/MCP). Wire up your existing infrastructure.

#### MCP Server Connections

**In OpenWebUI Admin Panel → Settings → Tools:**

1. **Mnemosyne** (memory/research)
   - Add as external tool server
   - URL: stdio command `python C:/Users/aaron/Desktop/tomb/scripts/mnemosyne_mcp.py`
   - Gives: memory_search, research_brief, memory_log, tomb_read

2. **Alphabetty** (search/browse/deep research)
   - SSE endpoint: `http://192.168.0.33:7700/sse`
   - Gives: search, chat, browse, agent_research, deep_research

3. **Context7** (library docs)
   - stdio: `npx -y @upstash/context7-mcp@latest`
   - Gives: resolve-library-id, query-docs

#### OpenWebUI Workspace Features to Enable

1. **Notes** — use as a scratchpad alongside agent chat
2. **Channels** — team channels where agent can post updates
3. **RAG** — upload docs/code for the agent to reference
4. **Code Interpreter** — Open Terminal already handles this
5. **Image Generation** — connect ComfyUI (port 8202) as a tool

#### UI Enhancements

OpenWebUI supports custom CSS and community themes. Add:
- Split-pane CSS for terminal + chat side by side
- Dark theme customization
- Keyboard shortcuts (already built into OpenWebUI)

#### Desktop Wrapper (Optional)

For a true desktop feel, wrap OpenWebUI in a lightweight Electron/Tauri shell:
```bash
# Using nativefier or PWA approach
# Or just add to desktop as a Chrome app:
# Chrome → Menu → More Tools → Create Shortcut → Open as Window
```

Or build a minimal Tauri wrapper (just a webview pointed at Lappy:3000):
```rust
// src-tauri/src/main.rs
fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

// tauri.conf.json
{
  "app": {
    "windows": [{
      "url": "http://192.168.0.33:3000",
      "title": "OpenWeb Claude Desktop"
    }]
  }
}
```

**Done when:** All MCP servers connected, agent has 20+ tools available.

---

## Quick Start Checklist

```bash
# 1. Verify everything is running on Lappy
ssh aaron@192.168.0.33 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# 2. Test Open Terminal directly
ssh aaron@192.168.0.33 "curl -s http://open-terminal:8000/health"
# Expected: {"status":"ok"}

# 3. Open OpenWebUI admin panel
# → http://192.168.0.33:3000
# → Admin Panel → Settings → Integrations → Open Terminal
# → Add connection (URL: http://open-terminal:8000, Key: a63a2a7ee2d5431d929c776122e3b706.hzHjrJlnfPd7cYfj)

# 4. Enable native function calling on a model
# → Workspace → Models → Edit model → Capabilities → Native Function Calling = ON

# 5. Test it
# → New chat → select terminal → ask "What OS are you running?"
```

---

## What You Get

| Feature | How |
|---------|-----|
| **Bash terminal** | Open Terminal (already running) |
| **File browser** | Open Terminal sidebar (built into OpenWebUI) |
| **Code execution** | Open Terminal (Python, Node, etc.) |
| **Web search** | Custom SearXNG tool |
| **Code search** | Custom ripgrep tool |
| **Git operations** | Custom git tool |
| **Memory** | Custom memory tool + Mnemosyne MCP |
| **Documentation lookup** | Context7 MCP |
| **Deep research** | Alphabetty MCP |
| **Multi-model** | LiteLLM proxy (Ollama local + cloud) |
| **RAG / docs** | OpenWebUI built-in |
| **Multi-user** | OpenWebUI built-in |
| **Mobile access** | OpenWebUI responsive UI |
| **Auth** | OpenWebUI built-in |

## Tool Inventory After All Phases

| # | Tool | Source | Phase |
|---|------|--------|-------|
| 1 | Bash execution | Open Terminal (built-in) | 1 |
| 2 | File read/write | Open Terminal (built-in) | 1 |
| 3 | File browser | Open Terminal (built-in) | 1 |
| 4 | Code execution | Open Terminal (built-in) | 1 |
| 5 | Web search | Custom tool (SearXNG) | 4 |
| 6 | Code search | Custom tool (ripgrep) | 4 |
| 7 | Git status/diff/log | Custom tool | 4 |
| 8 | Memory save/recall | Custom tool | 4 |
| 9 | URL fetcher | Custom tool | 4 |
| 10 | Docker manager | Custom tool | 4 |
| 11-28 | Mnemosyne tools | MCP server | 5 |
| 29-40+ | Alphabetty tools | MCP server | 5 |
| 41-42 | Context7 tools | MCP server | 5 |

**Total: ~42 tools available to the agent.**

## Time Estimate

| Phase | Time | Prerequisite |
|-------|------|-------------|
| 1. Connect Terminal | 30 min | OpenWebUI + Open Terminal running |
| 2. Model config | 1-2 hours | LiteLLM configured |
| 3. System prompt | 1-2 hours | Model with tool calling |
| 4. Custom tools | 2-3 days | OpenWebUI workspace |
| 5. MCP + Polish | 1-2 days | MCP servers running |
| **Total** | **~5-7 days** | |
