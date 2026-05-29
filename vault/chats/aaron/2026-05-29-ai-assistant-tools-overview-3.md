---
created: "2026-05-29 17:49:21"
updated: "2026-05-29 17:49:21"
tags: [chat, aaron]
user: "aaron"
model: "sloth-agent"
chat_id: "eaf477ab-9daf-4a12-8103-667b1b9e20ad"
tool_calls: [agent_list, agent_load]
message_count: 2
---

# 🛠️ AI Assistant Tools Overview

> aaron · 2026-05-29 17:49:21 · sloth-agent

## Messages

### User
Use agent_list to see what sub-agents are available, then use agent_load to inspect the researcher agent. Don't delegate yet, just report what you find.

### Assistant
I'll start by listing all available sub-agents, then load the researcher agent for inspection.Great, I can see 3 agents. Now let me load the **researcher** agent to inspect its full configuration.Here's a summary of what I found:

---

## Available Sub-Agents (3 Total)

| Agent | Purpose | Model |
|-------|---------|-------|
| **coder** | Code generation, debugging, code review | `zai-glm-5.1` |
| **researcher** | Deep research, multi-source analysis, fact-checking | `zai-glm-5.1` |
| **writer** | Prose, copywriting, reports, documentation | `zai-glm-5.1` |

---

## 🔬 Researcher Agent — Full Breakdown

**Description:** Deep research, multi-source analysis, fact-checking

**Model:** `zai-glm-5.1`

**Tools Available (5):**
| Tool | Purpose |
|------|---------|
| `search_and_read` | Search the web and read top results |
| `browse_page` | Navigate to a URL and read page content |
| `extract_data` | Extract structured data via JS expressions |
| `get_current_timestamp` | Get the current date/time |
| `ask_ai` | Consult another AI for a second opinion |

**System Prompt — Research Methodology:**
The researcher is instructed to:
1. **Search multiple sources** using `search_and_read`
2. **Browse specific pages** for deeper detail with `browse_page`
3. **Extract structured data** with `extract_data`
4. **Cross-reference claims** across sources
5. **Consult `ask_ai`** for second opinions on ambiguous findings

**Output Format (structured):**
- **Summary** — Key findings in 2–3 sentences
- **Details** — Full analysis with source citations
- **Confidence** — Reliability rating (high/medium/low)
- **Gaps** — What couldn't be verified
- **Sources** — List of URLs consulted

**Template Variables:** `{{ task }}`, `{{ date }}`, `{{ agent_name }}` — these are filled in at delegation time.

---

**Key Takeaway:** The researcher agent is well-equipped for multi-source web research with built-in cross-referencing and a confidence-rated output format. It's a good choice for any task requ

## Tools Used
agent_list, agent_load
