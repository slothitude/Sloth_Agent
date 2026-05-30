"""Telegram Bridge configuration — text-only."""
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# OpenWebUI
OPENWEBUI_BASE_URL = os.environ.get("OPENWEBUI_BASE_URL", "http://open-webui:8080")
OPENWEBUI_EMAIL = os.environ.get("OPENWEBUI_EMAIL", "aaron@slothitude.com")
OPENWEBUI_PASSWORD = os.environ.get("OPENWEBUI_PASSWORD", "Sloth2026!")
OPENWEBUI_MODEL = os.environ.get("OPENWEBUI_MODEL", "sloth-agent")

# Behavior
MAX_RESPONSE_CHARS = 4096
SESSION_TIMEOUT_HOURS = 24
