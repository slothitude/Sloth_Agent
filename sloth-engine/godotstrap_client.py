"""Sloth Engine — GodotStrap bridge client."""

from __future__ import annotations

import json

import httpx

from config import GODOTSTRAP_BRIDGE_URL, GODOTSTRAP_VIEWER_URL, GODOTSTRAP_EDITOR_URL


async def gs_health() -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{GODOTSTRAP_BRIDGE_URL}/health")
        return r.json() if r.status_code == 200 else {"status": "unreachable"}


async def gs_state() -> dict:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{GODOTSTRAP_BRIDGE_URL}/state")
        r.raise_for_status()
        return r.json()


async def gs_events(since: float | None = None) -> list:
    params = {"since": since} if since else None
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{GODOTSTRAP_BRIDGE_URL}/events", params=params)
        r.raise_for_status()
        return r.json()


async def gs_screenshot() -> bytes:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{GODOTSTRAP_BRIDGE_URL}/screenshot")
        r.raise_for_status()
        return r.content


async def gs_render(component_tree: dict) -> str:
    """Send component tree to GodotStrap bridge for rendering.
    Returns viewer iframe URL."""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{GODOTSTRAP_BRIDGE_URL}/render",
            json=component_tree,
        )
        r.raise_for_status()
        data = r.json()
        # Return the viewer URL (usually the same for iframe embedding)
        return data.get("viewer_url") or data.get("url") or GODOTSTRAP_VIEWER_URL


async def gs_write_scene(tscn_content: str, path: str = "/tmp/scene.tscn") -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{GODOTSTRAP_BRIDGE_URL}/scene/write",
            json={"content": tscn_content, "path": path},
        )
        r.raise_for_status()
        return r.json()


async def gs_open_scene(path: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{GODOTSTRAP_BRIDGE_URL}/scene/open",
            json={"path": path},
        )
        r.raise_for_status()
        return r.json()


async def gs_reset() -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{GODOTSTRAP_BRIDGE_URL}/reset")
        r.raise_for_status()
        return r.json()


async def gs_editor_url() -> str:
    """Return the Godot editor URL for embedding."""
    return GODOTSTRAP_EDITOR_URL
