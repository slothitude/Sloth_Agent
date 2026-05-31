"""Sloth Engine — Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Chat ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    chat_id: Optional[int] = None
    project_id: Optional[int] = None
    model: Optional[str] = None
    user_email: Optional[str] = None


class Message(BaseModel):
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None
    created_at: Optional[str] = None


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: FunctionCall


class FunctionCall(BaseModel):
    name: str
    arguments: str  # JSON string


# ── Projects ───────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    working_dir: str = ""


class Project(BaseModel):
    id: int
    user_email: str
    name: str
    description: str = ""
    working_dir: str = ""
    created_at: str = ""


# ── Conversations ──────────────────────────────────────────────────────────

class Conversation(BaseModel):
    id: int
    project_id: int
    user_email: str
    title: str
    created_at: str = ""


# ── Auth ──────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str
    email: str


# ── SSE events ────────────────────────────────────────────────────────────

class SSEEvent(BaseModel):
    type: str  # "token", "tool_call", "tool_result", "error", "done", "thinking"
    data: str = ""
