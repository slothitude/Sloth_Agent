"""Sloth Engine — Alphabetty HTTP client."""

from __future__ import annotations

import httpx

from config import ALPHABETTY_BASE, ALPHABETTY_BOOTSTRAP

_session_key: str | None = None


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if _session_key:
        h["Authorization"] = f"Bearer {_session_key}"
    return h


async def ensure_session() -> str:
    """Acquire or reuse an Alphabetty session."""
    global _session_key
    if _session_key:
        return _session_key

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{ALPHABETTY_BASE}/api/auth/session/acquire",
            headers={"X-Bootstrap-Token": ALPHABETTY_BOOTSTRAP},
            json={},
        )
        r.raise_for_status()
        data = r.json()
        _session_key = data.get("api_key") or data.get("key") or data.get("session_key") or data.get("token")
        if not _session_key:
            # Try nested response
            for v in data.values():
                if isinstance(v, str) and len(v) > 20:
                    _session_key = v
                    break
        if not _session_key:
            raise RuntimeError(f"Cannot extract session key from Alphabetty: {data}")
        return _session_key


async def alphabetty_get(path: str, params: dict | None = None) -> dict | list:
    await ensure_session()
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(f"{ALPHABETTY_BASE}{path}", headers=_headers(), params=params)
        r.raise_for_status()
        return r.json()


async def alphabetty_post(path: str, json_body: dict | None = None) -> dict | list:
    await ensure_session()
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{ALPHABETTY_BASE}{path}", headers=_headers(), json=json_body)
        r.raise_for_status()
        return r.json()
