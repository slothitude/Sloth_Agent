"""Sloth Engine — tool registry."""

from __future__ import annotations

import importlib

# Lazy import handler functions
_HANDLERS = None


def _h():
    global _HANDLERS
    if _HANDLERS is None:
        _HANDLERS = importlib.import_module("tool_handlers")
    return _HANDLERS


# ── Tool schemas (OpenAI function-calling format) ──────────────────────────

TOOL_SCHEMAS = [
    # --- Research & Search ---
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web using SearXNG. Returns ranked results with titles and URLs.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Search query"},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch a URL and return extracted text content.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"},
            }, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Fetch a URL via Alphabetty and return clean extracted text (markdown, cached).",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}, "format": {"type": "string", "default": "markdown"},
            }, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deep_research",
            "description": "Multi-round deep research on a complex topic. Returns comprehensive report with sources.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "depth": {"type": "integer", "default": 3},
                "mode": {"type": "string", "enum": ["concise", "detailed", "creative", "academic"], "default": "detailed"},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_and_read",
            "description": "Search the web and read top results in one call. Much faster than search then read separately.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "max_results": {"type": "integer", "default": 3},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_ai",
            "description": "Consult another AI model for a second opinion. Sends a message and returns full response with sources.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "mode": {"type": "string", "default": "concise"},
                "search_enabled": {"type": "boolean", "default": True},
            }, "required": ["query"]},
        },
    },

    # --- Bash & System ---
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Execute a bash command. host='local' for this machine, host='lappy' for Lappy (192.168.0.33).",
            "parameters": {"type": "object", "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "host": {"type": "string", "enum": ["local", "lappy"], "default": "local"},
            }, "required": ["command"]},
        },
    },

    # --- Files ---
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file's contents.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "File path to read"},
            }, "required": ["path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates parent directories if needed.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}, "content": {"type": "string"},
            }, "required": ["path", "content"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing old_text with new_text.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"},
            }, "required": ["path", "old_text", "new_text"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories at a path.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "default": "."},
            }},
        },
    },

    # --- Browser ---
    {
        "type": "function",
        "function": {
            "name": "browse_page",
            "description": "Navigate to a URL and return page content via Alphabetty CDP.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"},
            }, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot of the current browser page.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "Click an element by CSS selector via Alphabetty CDP.",
            "parameters": {"type": "object", "properties": {
                "selector": {"type": "string"},
            }, "required": ["selector"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into an element via Alphabetty CDP.",
            "parameters": {"type": "object", "properties": {
                "selector": {"type": "string"}, "text": {"type": "string"},
            }, "required": ["selector", "text"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_data",
            "description": "Extract data from the page using a JavaScript expression via Alphabetty CDP.",
            "parameters": {"type": "object", "properties": {
                "expression": {"type": "string"},
            }, "required": ["expression"]},
        },
    },

    # --- Vision ---
    {
        "type": "function",
        "function": {
            "name": "analyze_image",
            "description": "Analyze an image (URL or local path) with AI vision.",
            "parameters": {"type": "object", "properties": {
                "image_source": {"type": "string"}, "prompt": {"type": "string", "default": "Describe this image in detail"},
            }, "required": ["image_source"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate an image using ComfyUI via Alphabetty.",
            "parameters": {"type": "object", "properties": {
                "prompt": {"type": "string"}, "width": {"type": "integer", "default": 1024},
                "height": {"type": "integer", "default": 1024},
            }, "required": ["prompt"]},
        },
    },

    # --- Knowledge Graph ---
    {
        "type": "function",
        "function": {
            "name": "graph_search",
            "description": "Full-text search across conversations and entities in the knowledge graph.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "limit": {"type": "integer", "default": 10},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "graph_stats",
            "description": "Get knowledge graph statistics.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "entity_graph",
            "description": "Get an entity with its neighbors from the knowledge graph.",
            "parameters": {"type": "object", "properties": {
                "entity_name": {"type": "string"}, "depth": {"type": "integer", "default": 2},
            }, "required": ["entity_name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tags",
            "description": "List all tags in the knowledge graph.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_spaces",
            "description": "List all knowledge graph spaces.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_conversations",
            "description": "List all Alphabetty conversations with previews and tags.",
            "parameters": {"type": "object", "properties": {}},
        },
    },

    # --- Vault (Obsidian) ---
    {
        "type": "function",
        "function": {
            "name": "vault_list",
            "description": "List vault directory contents.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "default": ""},
            }},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vault_read",
            "description": "Read a vault note by path.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
            }, "required": ["path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vault_write",
            "description": "Write a note to the vault. Auto-adds frontmatter if missing.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}, "content": {"type": "string"},
            }, "required": ["path", "content"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vault_search",
            "description": "Full-text search across vault notes.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "max_results": {"type": "integer", "default": 10},
            }, "required": ["query"]},
        },
    },

    # --- Artifacts ---
    {
        "type": "function",
        "function": {
            "name": "create_artifact",
            "description": "Create a sandboxed code artifact for preview (HTML, SVG, React, JS, Mermaid, Python, CSS).",
            "parameters": {"type": "object", "properties": {
                "title": {"type": "string"}, "source": {"type": "string"},
                "type": {"type": "string", "enum": ["html", "svg", "react", "javascript", "mermaid", "python", "code", "css"], "default": "html"},
            }, "required": ["source"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_artifacts",
            "description": "List all stored artifacts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_artifact",
            "description": "Update source code of an existing artifact.",
            "parameters": {"type": "object", "properties": {
                "id": {"type": "string"}, "source": {"type": "string"},
            }, "required": ["id", "source"]},
        },
    },

    # --- Voice ---
    {
        "type": "function",
        "function": {
            "name": "speech_to_text",
            "description": "Transcribe audio (base64 WAV/MP3) to text using Whisper STT.",
            "parameters": {"type": "object", "properties": {
                "audio_base64": {"type": "string", "description": "Base64-encoded audio data"},
                "language": {"type": "string", "description": "Language code (optional, auto-detect if omitted)"},
            }, "required": ["audio_base64"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "text_to_speech",
            "description": "Convert text to speech using Kokoro TTS. Returns base64 WAV audio.",
            "parameters": {"type": "object", "properties": {
                "text": {"type": "string"}, "voice": {"type": "string", "default": "af_bella"},
                "speed": {"type": "number", "default": 1.0},
            }, "required": ["text"]},
        },
    },

    # --- Skills ---
    {
        "type": "function",
        "function": {
            "name": "skill_list",
            "description": "List all available skill templates in vault/skills/.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_load",
            "description": "Load a skill template to see its content and variables.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_execute",
            "description": "Execute a skill template with variables, returns the rendered prompt.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"},
                "variables": {"type": "string", "description": "JSON object or key=value pairs"},
            }, "required": ["name"]},
        },
    },

    # --- Sub-Agents ---
    {
        "type": "function",
        "function": {
            "name": "agent_list",
            "description": "List all available agent templates in vault/agents/.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agent_load",
            "description": "Load an agent template to see its full system prompt and config.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to",
            "description": "Delegate a task to a sub-agent. The agent runs with its own tools and system prompt.",
            "parameters": {"type": "object", "properties": {
                "agent_id": {"type": "string"}, "message": {"type": "string"},
            }, "required": ["agent_id", "message"]},
        },
    },

    # --- Workflows (n8n) ---
    {
        "type": "function",
        "function": {
            "name": "workflow_create",
            "description": "Create an n8n workflow from JSON nodes and connections.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"}, "nodes": {"type": "string", "default": "[]"},
                "connections": {"type": "string", "default": "{}"}, "active": {"type": "boolean", "default": False},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workflow_list",
            "description": "List all n8n workflows with status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workflow_run",
            "description": "Trigger an n8n workflow execution.",
            "parameters": {"type": "object", "properties": {
                "workflow_id": {"type": "string"}, "data": {"type": "string", "default": "{}"},
            }, "required": ["workflow_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workflow_status",
            "description": "Check execution history for a workflow.",
            "parameters": {"type": "object", "properties": {
                "workflow_id": {"type": "string"}, "limit": {"type": "integer", "default": 10},
            }, "required": ["workflow_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workflow_delete",
            "description": "Delete an n8n workflow by ID.",
            "parameters": {"type": "object", "properties": {
                "workflow_id": {"type": "string"},
            }, "required": ["workflow_id"]},
        },
    },

    # --- Sign-in Automation ---
    {
        "type": "function",
        "function": {
            "name": "signin_start",
            "description": "Start a sign-in flow for a website.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}, "username": {"type": "string"}, "password": {"type": "string"},
            }, "required": ["url", "username", "password"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "signin_auto",
            "description": "Sign in using a saved credential profile (handles 2FA automatically).",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "signin_status",
            "description": "Get current sign-in workflow state.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "signin_submit_2fa",
            "description": "Submit a 2FA code during sign-in.",
            "parameters": {"type": "object", "properties": {
                "code": {"type": "string"},
            }, "required": ["code"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "signin_check_2fa",
            "description": "Check if the current page is asking for 2FA/verification code.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "signin_save",
            "description": "Save a credential profile for auto sign-in.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"}, "url": {"type": "string"},
                "username": {"type": "string"}, "password": {"type": "string"},
                "totp_secret": {"type": "string", "default": ""},
                "selectors": {"type": "string", "default": ""},
            }, "required": ["name", "url", "username", "password"]},
        },
    },

    # --- Macros ---
    {
        "type": "function",
        "function": {
            "name": "macro_record_start",
            "description": "Start recording browser actions as a reusable macro.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"}, "url": {"type": "string", "default": ""},
            }, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "macro_record_stop",
            "description": "Stop macro recording and save.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "macro_play",
            "description": "Replay a saved macro.",
            "parameters": {"type": "object", "properties": {
                "macro_id": {"type": "integer"},
            }, "required": ["macro_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "macro_list",
            "description": "List all saved macros.",
            "parameters": {"type": "object", "properties": {}},
        },
    },

    # --- Video ---
    {
        "type": "function",
        "function": {
            "name": "youtube_play",
            "description": "Search YouTube and play the first result.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_video",
            "description": "Play any video URL (YouTube, Twitter, Instagram, TikTok, etc.).",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"},
            }, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_embed",
            "description": "Search YouTube and return an embeddable video that plays inline in the chat. Use this when the user wants to watch a video in the browser.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "video_embed",
            "description": "Embed a video URL inline in the chat. Works with YouTube, direct video URLs, etc.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"},
            }, "required": ["url"]},
        },
    },

    # --- Files & Downloads ---
    {
        "type": "function",
        "function": {
            "name": "upload_file",
            "description": "Upload a local file for analysis (PDF, DOCX, images, code).",
            "parameters": {"type": "object", "properties": {
                "file_path": {"type": "string"}, "query": {"type": "string", "default": ""},
            }, "required": ["file_path"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_save",
            "description": "Download a file from URL to the server's download directory.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string"}, "filename": {"type": "string", "default": ""},
                "subdir": {"type": "string", "default": ""},
            }, "required": ["url"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "download_list",
            "description": "List files in the download directory.",
            "parameters": {"type": "object", "properties": {
                "subdir": {"type": "string", "default": ""},
            }},
        },
    },

    # --- Media Stack (Radarr, Sonarr, qBittorrent, Jellyfin, Jellyseerr) ---
    {
        "type": "function",
        "function": {
            "name": "media_search",
            "description": "Search Jellyfin library for movies/TV shows. Returns direct-play stream links (no login).",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Search term"},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tmdb",
            "description": "Search TMDb via Jellyseerr for movies or TV shows to request/download.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"},
                "media_type": {"type": "string", "enum": ["movie", "tv"], "default": "movie"},
            }, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_request",
            "description": "Request a movie or TV show via Jellyseerr (triggers Radarr/Sonarr download).",
            "parameters": {"type": "object", "properties": {
                "media_id": {"type": "integer"},
                "media_type": {"type": "string", "enum": ["movie", "tv"]},
            }, "required": ["media_id", "media_type"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_requests",
            "description": "List Jellyseerr requests (pending, approved, available).",
            "parameters": {"type": "object", "properties": {
                "status": {"type": "string", "default": ""},
            }, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "radarr_movies",
            "description": "List movies in Radarr library.",
            "parameters": {"type": "object", "properties": {
                "status": {"type": "string", "default": ""},
            }, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "radarr_queue",
            "description": "Check Radarr download queue.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sonarr_series",
            "description": "List series in Sonarr library.",
            "parameters": {"type": "object", "properties": {
                "status": {"type": "string", "default": ""},
            }, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sonarr_queue",
            "description": "Check Sonarr download queue.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "torrents_list",
            "description": "List torrents from qBittorrent with status/progress/speed.",
            "parameters": {"type": "object", "properties": {
                "filter_status": {"type": "string", "default": ""},
            }, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "torrents_action",
            "description": "Manage a torrent: pause, resume, delete, delete_files, or bump (move to top of queue).",
            "parameters": {"type": "object", "properties": {
                "hash": {"type": "string", "description": "Torrent hash"},
                "action": {"type": "string", "enum": ["pause", "resume", "delete", "delete_files", "bump"], "default": "pause"},
            }, "required": ["hash", "action"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_stack_status",
            "description": "Show all media containers + VPN + disk space.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vpn_status",
            "description": "Check Gluetun VPN connection (IP, location).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },

    # --- Agentic Build Methodology ---
    {
        "type": "function",
        "function": {
            "name": "plan_create",
            "description": "Create a structured plan with ordered steps for a build task. Sets the first step active. Provide project context (build/test/lint commands) for automated verification.",
            "parameters": {"type": "object", "properties": {
                "project_id": {"type": "integer", "description": "Project ID"},
                "plan_name": {"type": "string", "description": "Plan name"},
                "steps": {"type": "string", "description": "JSON array of {\"title\": \"...\", \"description\": \"...\"}"},
                "build_cmd": {"type": "string", "default": "", "description": "Build command (e.g. 'npm run build')"},
                "test_cmd": {"type": "string", "default": "", "description": "Test command (e.g. 'npm test')"},
                "lint_cmd": {"type": "string", "default": "", "description": "Lint command (e.g. 'npm run lint')"},
                "repo_root": {"type": "string", "default": "", "description": "Repository root directory"},
                "language": {"type": "string", "default": "", "description": "Programming language"},
                "framework": {"type": "string", "default": "", "description": "Framework (e.g. React, Flask)"},
            }, "required": ["project_id", "plan_name", "steps"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_next",
            "description": "Get the current active step. Returns step title, description, project context, retry count, and accumulated errors. If no active step, returns 'all done' summary.",
            "parameters": {"type": "object", "properties": {
                "project_id": {"type": "integer", "description": "Project ID"},
            }, "required": ["project_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_complete",
            "description": "Mark the current active step as done and auto-advance to the next pending step. Call this after verifying a step passed.",
            "parameters": {"type": "object", "properties": {
                "project_id": {"type": "integer", "description": "Project ID"},
                "result": {"type": "string", "default": "", "description": "Summary of what was accomplished"},
            }, "required": ["project_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_fail",
            "description": "Mark the current active step as failed. If retry=true, keeps the step active with error appended for next attempt. Max 3 retries per step. If retry=false, marks failed and advances to next step.",
            "parameters": {"type": "object", "properties": {
                "project_id": {"type": "integer", "description": "Project ID"},
                "error": {"type": "string", "default": "", "description": "What went wrong"},
                "retry": {"type": "boolean", "default": True, "description": "Whether to retry the step"},
            }, "required": ["project_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "project_context",
            "description": "Set or get project build context (build_cmd, test_cmd, lint_cmd, repo_root, language, framework). If no args provided, returns current context.",
            "parameters": {"type": "object", "properties": {
                "project_id": {"type": "integer", "description": "Project ID"},
                "build_cmd": {"type": "string", "default": ""},
                "test_cmd": {"type": "string", "default": ""},
                "lint_cmd": {"type": "string", "default": ""},
                "repo_root": {"type": "string", "default": ""},
                "language": {"type": "string", "default": ""},
                "framework": {"type": "string", "default": ""},
            }, "required": ["project_id"]},
        },
    },

    # --- Thinking ---
    {
        "type": "function",
        "function": {
            "name": "thinking_log",
            "description": "Save a reasoning trace to vault/thinking/ for transparency.",
            "parameters": {"type": "object", "properties": {
                "title": {"type": "string"}, "reasoning": {"type": "string"},
                "conclusion": {"type": "string", "default": ""},
            }, "required": ["title", "reasoning"]},
        },
    },

    # --- GodotStrap ---
    {
        "type": "function",
        "function": {
            "name": "render_component",
            "description": "Send a JSON component tree to GodotStrap bridge for rendering. Returns viewer iframe URL.",
            "parameters": {"type": "object", "properties": {
                "component_tree": {"type": "object", "description": "JSON component tree for Godot to render"},
            }, "required": ["component_tree"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gs_health",
            "description": "Check GodotStrap bridge health.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gs_state",
            "description": "Get current GodotStrap bridge state.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gs_events",
            "description": "Get GodotStrap UI events (clicks, inputs, etc.).",
            "parameters": {"type": "object", "properties": {
                "since": {"type": "number", "description": "Timestamp to get events after"},
            }},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gs_screenshot",
            "description": "Take a screenshot of the current GodotStrap canvas.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gs_reset",
            "description": "Reset the GodotStrap canvas to blank state.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_scene",
            "description": "Write a .tscn scene file to GodotStrap bridge.",
            "parameters": {"type": "object", "properties": {
                "tscn_content": {"type": "string"}, "path": {"type": "string", "default": "/tmp/scene.tscn"},
            }, "required": ["tscn_content"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_scene",
            "description": "Open a .tscn scene file in GodotStrap bridge.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
            }, "required": ["path"]},
        },
    },
]


# ── Registry ────────────────────────────────────────────────────────────────

# Map tool name -> handler function name
TOOL_DISPATCH = {
    "search_web": "execute_search_web",
    "fetch_url": "execute_fetch_url",
    "read_url": "execute_read_url",
    "deep_research": "execute_deep_research",
    "search_and_read": "execute_search_and_read",
    "ask_ai": "execute_ask_ai",
    "execute_bash": "execute_bash",
    "read_file": "execute_read_file",
    "write_file": "execute_write_file",
    "edit_file": "execute_edit_file",
    "list_directory": "execute_list_directory",
    "browse_page": "execute_browse_page",
    "screenshot": "execute_screenshot",
    "click_element": "execute_click_element",
    "type_text": "execute_type_text",
    "extract_data": "execute_extract_data",
    "analyze_image": "execute_analyze_image",
    "generate_image": "execute_generate_image",
    "graph_search": "execute_graph_search",
    "graph_stats": "execute_graph_stats",
    "entity_graph": "execute_entity_graph",
    "list_tags": "execute_list_tags",
    "list_spaces": "execute_list_spaces",
    "list_conversations": "execute_list_conversations",
    "vault_list": "execute_vault_list",
    "vault_read": "execute_vault_read",
    "vault_write": "execute_vault_write",
    "vault_search": "execute_vault_search",
    "create_artifact": "execute_create_artifact",
    "list_artifacts": "execute_list_artifacts",
    "update_artifact": "execute_update_artifact",
    "speech_to_text": "execute_speech_to_text",
    "text_to_speech": "execute_text_to_speech",
    "skill_list": "execute_skill_list",
    "skill_load": "execute_skill_load",
    "skill_execute": "execute_skill_execute",
    "agent_list": "execute_agent_list",
    "agent_load": "execute_agent_load",
    "delegate_to": "execute_delegate_to",
    "workflow_create": "execute_workflow_create",
    "workflow_list": "execute_workflow_list",
    "workflow_run": "execute_workflow_run",
    "workflow_status": "execute_workflow_status",
    "workflow_delete": "execute_workflow_delete",
    "signin_start": "execute_signin_start",
    "signin_auto": "execute_signin_auto",
    "signin_status": "execute_signin_status",
    "signin_submit_2fa": "execute_signin_submit_2fa",
    "signin_check_2fa": "execute_signin_check_2fa",
    "signin_save": "execute_signin_save",
    "macro_record_start": "execute_macro_record_start",
    "macro_record_stop": "execute_macro_record_stop",
    "macro_play": "execute_macro_play",
    "macro_list": "execute_macro_list",
    "youtube_play": "execute_youtube_play",
    "play_video": "execute_play_video",
    "youtube_embed": "execute_youtube_embed",
    "video_embed": "execute_video_embed",
    "upload_file": "execute_upload_file",
    "download_save": "execute_download_save",
    "download_list": "execute_download_list",
    "media_search": "execute_media_search",
    "search_tmdb": "execute_search_tmdb",
    "media_request": "execute_media_request",
    "media_requests": "execute_media_requests",
    "radarr_movies": "execute_radarr_movies",
    "radarr_queue": "execute_radarr_queue",
    "sonarr_series": "execute_sonarr_series",
    "sonarr_queue": "execute_sonarr_queue",
    "torrents_list": "execute_torrents_list",
    "torrents_action": "execute_torrents_action",
    "media_stack_status": "execute_media_stack_status",
    "vpn_status": "execute_vpn_status",
    "thinking_log": "execute_thinking_log",
    "plan_create": "execute_plan_create",
    "todo_next": "execute_todo_next",
    "todo_complete": "execute_todo_complete",
    "todo_fail": "execute_todo_fail",
    "project_context": "execute_project_context",
    "render_component": "execute_render_component",
    "gs_health": "execute_gs_health",
    "gs_state": "execute_gs_state",
    "gs_events": "execute_gs_events",
    "gs_screenshot": "execute_gs_screenshot",
    "gs_reset": "execute_gs_reset",
    "write_scene": "execute_write_scene",
    "open_scene": "execute_open_scene",
}


def get_all_schemas() -> list[dict]:
    """Return all tool schemas in OpenAI format for LLM injection."""
    return list(TOOL_SCHEMAS)


def get_schemas_for_tools(tool_names: list[str]) -> list[dict]:
    """Return only schemas for specified tool names."""
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in tool_names]


async def dispatch_tool(name: str, args: dict) -> str:
    """Dispatch a tool call to its handler. Sync handlers run in a thread pool."""
    import asyncio
    handler_name = TOOL_DISPATCH.get(name)
    if not handler_name:
        return f"Error: Unknown tool '{name}'"

    handler = getattr(_h(), handler_name, None)
    if not handler:
        return f"Error: Handler '{handler_name}' not found"

    try:
        if asyncio.iscoroutinefunction(handler):
            result = await handler(**args)
        else:
            # Run sync handlers in thread pool to avoid blocking event loop
            result = await asyncio.to_thread(handler, **args)
        return str(result)
    except TypeError as e:
        return f"Error calling {name}: {e}"
    except Exception as e:
        return f"Error: {e}"
