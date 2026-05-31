"""Sloth Engine — configuration."""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
VAULT_DIR = BASE_DIR / "vault"
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

VAULT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "sloth_engine.db"

# ── Server ─────────────────────────────────────────────────────────────────
HOST = os.getenv("SLOTH_HOST", "0.0.0.0")
PORT = int(os.getenv("SLOTH_PORT", "3001"))
DEBUG = os.getenv("SLOTH_DEBUG", "false").lower() == "true"

# ── Z.ai GLM-5.1 (primary LLM) ────────────────────────────────────────────
ZAI_API_KEY = os.getenv("ZAI_API_KEY", "38ae1c3d06494328a60484cabb7552eb.M2RxlwRGFgD8R4GM").strip()
ZAI_BASE_URL = os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/coding/paas/v4")
DEFAULT_MODEL = os.getenv("SLOTH_DEFAULT_MODEL", "glm-5.1")
MAX_TOOL_ROUNDS = int(os.getenv("SLOTH_MAX_TOOL_ROUNDS", "25"))

# ── Ollama (secondary, optional) ─────────────────────────────────────────
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")

# ── SearXNG ───────────────────────────────────────────────────────────────
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://100.84.161.63:8888")

# ── Alphabetty ────────────────────────────────────────────────────────────
ALPHABETTY_BASE = os.getenv("ALPHABETTY_BASE", "http://100.84.161.63:7700")
ALPHABETTY_BOOTSTRAP = os.getenv("ALPHABETTY_BOOTSTRAP", "alphabetty-bootstrap-secret")

# ── Artifact server ────────────────────────────────────────────────────────
ARTIFACT_BASE = os.getenv("ARTIFACT_BASE", "http://100.84.161.63:8012")

# ── Audio stack (TTS/STT) ───────────────────────────────────────────────────
AUDIO_BASE = os.getenv("AUDIO_BASE", "http://100.84.161.63:8005")
STT_BASE = os.getenv("STT_BASE", "http://100.84.161.63:8006")

# ── Media Stack ──────────────────────────────────────────────────────────
MEDIA_API_BASE = os.getenv("MEDIA_API_BASE", "http://localhost:8070")
MEDIA_API_KEY = os.getenv("MEDIA_API_KEY", "")

# ── GodotStrap ─────────────────────────────────────────────────────────────
GODOTSTRAP_BRIDGE_URL = os.getenv("GODOTSTRAP_BRIDGE_URL", "http://localhost:7777")
GODOTSTRAP_VIEWER_URL = os.getenv("GODOTSTRAP_VIEWER_URL", "http://localhost:7778")
GODOTSTRAP_EDITOR_URL = os.getenv("GODOTSTRAP_EDITOR_URL", "http://localhost:7790/editor/")

# ── File system restrictions ──────────────────────────────────────────────
ALLOWED_ROOTS = os.getenv("SLOTH_ALLOWED_ROOTS", "").split(",")
if not ALLOWED_ROOTS or ALLOWED_ROOTS == [""]:
    ALLOWED_ROOTS = [
        str(VAULT_DIR),
        os.getenv("HOME", str(Path.home())),
        "C:/Users/aaron/Desktop",
        "C:/Users/aaron/Documents",
        "D:/Sloth_Agent",
    ]

# ── Bash restrictions ────────────────────────────────────────────────────
BASH_BLOCKLIST = {
    "rm -rf /",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "format",
    "del /f /s /q C:",
}

# ── Auth ──────────────────────────────────────────────────────────────────
API_KEY_SALT = os.getenv("SLOTH_KEY_SALT", "sloth-engine-salt-2026")
ADMIN_TOKEN = os.getenv("SLOTH_ADMIN_TOKEN", "")
