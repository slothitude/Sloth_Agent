"""Per-user session store — maps Telegram user_id to message history + chat_id."""
import time

_sessions: dict[int, dict] = {}  # user_id -> {"messages": [...], "chat_id": ..., "updated": ...}

TIMEOUT = 24 * 3600  # 24 hours


def get_session(user_id: int) -> dict:
    """Return session dict for user, or create fresh one."""
    s = _sessions.get(user_id)
    if not s or time.time() - s["updated"] > TIMEOUT:
        _sessions[user_id] = {"messages": [], "chat_id": None, "updated": time.time()}
    s = _sessions[user_id]
    s["updated"] = time.time()
    return s


def clear(user_id: int):
    """Clear session for a user (e.g. /reset command)."""
    _sessions.pop(user_id, None)
