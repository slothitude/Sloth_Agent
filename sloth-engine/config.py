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

WORKSPACE_DIR = VAULT_DIR / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

# Workspace files that must exist to skip bootstrap
WORKSPACE_FILES = ["soul.md", "identity.md", "user.md"]

DB_PATH = DATA_DIR / "sloth_engine.db"

# ── Server ─────────────────────────────────────────────────────────────────
HOST = os.getenv("SLOTH_HOST", "0.0.0.0")
PORT = int(os.getenv("SLOTH_PORT", "3001"))
DEBUG = os.getenv("SLOTH_DEBUG", "false").lower() == "true"

# ── Z.ai GLM-5.1 (primary LLM) ────────────────────────────────────────────
ZAI_API_KEY = os.getenv("ZAI_API_KEY", "").strip()
if not ZAI_API_KEY:
    raise RuntimeError("ZAI_API_KEY environment variable is required")
ZAI_BASE_URL = os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/coding/paas/v4")
DEFAULT_MODEL = os.getenv("SLOTH_DEFAULT_MODEL", "glm-5.1")
MAX_TOOL_ROUNDS = int(os.getenv("SLOTH_MAX_TOOL_ROUNDS", "25"))

# ── Ollama (secondary, optional) ─────────────────────────────────────────
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")

# ── SearXNG ───────────────────────────────────────────────────────────────
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://100.84.161.63:8888")

# ── Alphabetty ────────────────────────────────────────────────────────────
ALPHABETTY_BASE = os.getenv("ALPHABETTY_BASE", "http://100.84.161.63:7700")
ALPHABETTY_BOOTSTRAP = os.getenv("ALPHABETTY_BOOTSTRAP", "")

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
# Dangerous patterns checked via regex against shell-split tokens
BASH_DANGEROUS_PATTERNS = [
    r"^rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)*(-[a-zA-Z]*r[a-zA-Z]*\s+)*(/\s|/\*$)",
    r"mkfs",
    r"\bdd\b.*\bif=",
    r":\(\)\s*\{",
    r"\bformat\b",
    r">\s*/dev/",
    r"\bchmod\b.*777\s+/",
    r"\bchown\b.*-R\s+/",
    r"\biptables\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\binit\b\s+[06]",
    r"\bmount\b.*/\s",
    r"\bumount\b.*/\s",
    r"\bsystemctl\b.*(stop|disable|mask)\s+",
    r"\bpasswd\b",
    r"\buseradd\b",
    r"\buserdel\b",
    r"\bgroupadd\b",
    r"\bcrontab\b",
    r"\bcurl\b.*\|\s*bash",
    r"\bwget\b.*\|\s*bash",
    r"\bsudo\b",
]

# ── Auth ──────────────────────────────────────────────────────────────────
API_KEY_SALT = os.getenv("SLOTH_KEY_SALT", "")
if not API_KEY_SALT:
    API_KEY_SALT = os.urandom(32).hex()
ADMIN_TOKEN = os.getenv("SLOTH_ADMIN_TOKEN", "")
