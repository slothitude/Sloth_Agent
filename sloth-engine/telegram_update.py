"""Sloth Engine — Telegram bridge update instructions.

The existing telegram-bridge (D:\Sloth_Agent\telegram-bridge\) needs these changes:

1. In .env (on Lappy):
   OLD: OPENWEBUI_BASE_URL=http://open-webui:8080
   NEW: OPENWEBUI_BASE_URL=http://localhost:3001

2. In openwebui_client.py:
   - Change the API path from /api/chat/completions to /api/chat
   - Remove tool_ids from request body (not needed by Sloth Engine)
   - Keep the streaming tool loop — parse SSE events from new engine format
   - New SSE event types: token, thinking, tool_result, tool_calls, error, done
   - Response format: data: {"type": "token", "content": "..."}

3. Auth:
   - Use Bearer token: sloth-engine-admin-token (default admin token)
   - Header: Authorization: Bearer sloth-engine-admin-token

4. After updating, rebuild:
   cd D:/Sloth_Agent/telegram-bridge
   docker compose build --no-cache
   docker compose up -d

This file is a reference. The actual changes need to be made on Lappy.
"""
