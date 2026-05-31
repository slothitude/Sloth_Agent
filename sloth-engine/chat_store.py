"""Sloth Engine — chat store (SQLite)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                working_dir TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                user_email TEXT NOT NULL,
                title TEXT DEFAULT 'New Chat',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('system','user','assistant','tool')),
                content TEXT DEFAULT '',
                tool_calls TEXT,
                tool_call_id TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_convs_project ON conversations(project_id);
            CREATE INDEX IF NOT EXISTS idx_convs_user ON conversations(user_email);
            CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_email);
        """)
        db.commit()


# ── Projects ───────────────────────────────────────────────────────────────

def create_project(user_email: str, name: str, description: str = "", working_dir: str = "") -> dict:
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            "INSERT INTO projects (user_email, name, description, working_dir) VALUES (?, ?, ?, ?)",
            (user_email, name, description, working_dir),
        )
        db.commit()
        return dict(id=cur.lastrowid, user_email=user_email, name=name,
                     description=description, working_dir=working_dir,
                     created_at=datetime.utcnow().isoformat())


def list_projects(user_email: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT id, name, description, working_dir, created_at FROM projects WHERE user_email = ? ORDER BY id",
            (user_email,),
        ).fetchall()
        return [dict(id=r[0], name=r[1], description=r[2], working_dir=r[3], created_at=r[4]) for r in rows]


def get_project(project_id: int) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT id, user_email, name, description, working_dir, created_at FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if row:
            return dict(id=row[0], user_email=row[1], name=row[2],
                         description=row[3], working_dir=row[4], created_at=row[5])
    return None


def delete_project(project_id: int, user_email: str) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            "DELETE FROM projects WHERE id = ? AND user_email = ?",
            (project_id, user_email),
        )
        db.commit()
        return cur.rowcount > 0


# ── Conversations ──────────────────────────────────────────────────────────

def create_conversation(user_email: str, project_id: Optional[int] = None, title: str = "New Chat") -> dict:
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            "INSERT INTO conversations (user_email, project_id, title) VALUES (?, ?, ?)",
            (user_email, project_id, title),
        )
        db.commit()
        return dict(id=cur.lastrowid, project_id=project_id or 0,
                     user_email=user_email, title=title,
                     created_at=datetime.utcnow().isoformat())


def list_conversations(user_email: str, project_id: Optional[int] = None, limit: int = 50) -> list[dict]:
    with sqlite3.connect(DB_PATH) as db:
        if project_id:
            rows = db.execute(
                "SELECT id, project_id, title, created_at FROM conversations WHERE user_email = ? AND project_id = ? ORDER BY id DESC LIMIT ?",
                (user_email, project_id, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, project_id, title, created_at FROM conversations WHERE user_email = ? ORDER BY id DESC LIMIT ?",
                (user_email, limit),
            ).fetchall()
        return [dict(id=r[0], project_id=r[1], title=r[2], created_at=r[3]) for r in rows]


def get_conversation(conversation_id: int) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT id, project_id, user_email, title, created_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if row:
            return dict(id=row[0], project_id=row[1], user_email=row[2],
                         title=row[3], created_at=row[4])
    return None


def update_conversation_title(conversation_id: int, title: str):
    with sqlite3.connect(DB_PATH) as db:
        db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
        db.commit()


def delete_conversation(conversation_id: int, user_email: str) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            "DELETE FROM conversations WHERE id = ? AND user_email = ?",
            (conversation_id, user_email),
        )
        db.commit()
        return cur.rowcount > 0


# ── Messages ────────────────────────────────────────────────────────────────

def add_message(conversation_id: int, role: str, content: str,
                tool_calls: Optional[str] = None, tool_call_id: Optional[str] = None) -> int:
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            "INSERT INTO messages (conversation_id, role, content, tool_calls, tool_call_id) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, tool_calls, tool_call_id),
        )
        db.commit()
        return cur.lastrowid


def get_messages(conversation_id: int, limit: int = 200) -> list[dict]:
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT id, role, content, tool_calls, tool_call_id, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
        return [
            dict(id=r[0], role=r[1], content=r[2], tool_calls=r[3],
                 tool_call_id=r[4], created_at=r[5])
            for r in rows
        ]


def get_messages_for_llm(conversation_id: int) -> list[dict]:
    """Return messages in OpenAI format for the LLM API."""
    msgs = get_messages(conversation_id)
    out = []
    for m in msgs:
        msg = {"role": m["role"], "content": m["content"]}
        if m["tool_calls"]:
            import json
            try:
                msg["tool_calls"] = json.loads(m["tool_calls"])
            except (json.JSONDecodeError, TypeError):
                pass
        if m["tool_call_id"]:
            msg["tool_call_id"] = m["tool_call_id"]
        out.append(msg)
    return out
