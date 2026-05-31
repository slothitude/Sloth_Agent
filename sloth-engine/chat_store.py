"""Sloth Engine — chat store (SQLite)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from config import DB_PATH


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA busy_timeout = 5000")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                working_dir TEXT DEFAULT '',
                context TEXT DEFAULT '{}',
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

            CREATE TABLE IF NOT EXISTS plan_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                plan_name TEXT NOT NULL,
                step_num INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','done','failed')),
                result TEXT DEFAULT '',
                error TEXT DEFAULT '',
                retry_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_convs_project ON conversations(project_id);
            CREATE INDEX IF NOT EXISTS idx_convs_user ON conversations(user_email);
            CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_email);
            CREATE INDEX IF NOT EXISTS idx_plan_steps_project ON plan_steps(project_id);
        """)

        # Migrate: add context column to existing projects table
        try:
            db.execute("SELECT context FROM projects LIMIT 0")
        except sqlite3.OperationalError:
            db.execute("ALTER TABLE projects ADD COLUMN context TEXT DEFAULT '{}'")
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
                     created_at=datetime.now(timezone.utc).isoformat())


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
                     created_at=datetime.now(timezone.utc).isoformat())


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


# ── Plan Steps ───────────────────────────────────────────────────────────────

def create_plan(project_id: int, plan_name: str, steps: list[dict],
                build_cmd: str = "", test_cmd: str = "", lint_cmd: str = "",
                repo_root: str = "", language: str = "", framework: str = "") -> dict:
    """Create a plan with ordered steps for a project."""
    import json as _json
    with sqlite3.connect(DB_PATH) as db:
        # Store project context
        ctx = {}
        if build_cmd: ctx["build_cmd"] = build_cmd
        if test_cmd: ctx["test_cmd"] = test_cmd
        if lint_cmd: ctx["lint_cmd"] = lint_cmd
        if repo_root: ctx["repo_root"] = repo_root
        if language: ctx["language"] = language
        if framework: ctx["framework"] = framework
        if ctx:
            db.execute("UPDATE projects SET context = ? WHERE id = ?", (_json.dumps(ctx), project_id))

        # Clear any existing active steps for this project
        db.execute("UPDATE plan_steps SET status = 'failed' WHERE project_id = ? AND status = 'active'", (project_id,))

        # Insert steps
        step_ids = []
        for i, step in enumerate(steps):
            cur = db.execute(
                "INSERT INTO plan_steps (project_id, plan_name, step_num, title, description, status) VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, plan_name, i + 1, step.get("title", f"Step {i+1}"),
                 step.get("description", ""), "active" if i == 0 else "pending"),
            )
            step_ids.append(cur.lastrowid)
        db.commit()
        return {"plan_name": plan_name, "total_steps": len(steps), "step_ids": step_ids}


def get_active_step(project_id: int) -> Optional[dict]:
    """Get the current active step for a project, or None if all done."""
    import json as _json
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT id, step_num, title, description, retry_count, error FROM plan_steps WHERE project_id = ? AND status = 'active' ORDER BY step_num LIMIT 1",
            (project_id,),
        ).fetchone()
        if not row:
            return None
        # Get project context
        proj = db.execute("SELECT context FROM projects WHERE id = ?", (project_id,)).fetchone()
        ctx = _json.loads(proj[0]) if proj and proj[0] else {}
        return {
            "id": row[0], "step_num": row[1], "title": row[2],
            "description": row[3], "retry_count": row[4], "error": row[5],
            "project_context": ctx,
        }


def complete_step(project_id: int, result: str = "") -> Optional[dict]:
    """Mark active step as done, advance to next pending step."""
    with sqlite3.connect(DB_PATH) as db:
        # Mark current active step as done
        db.execute(
            "UPDATE plan_steps SET status = 'done', result = ?, updated_at = datetime('now') WHERE project_id = ? AND status = 'active'",
            (result, project_id),
        )
        # Find next pending step
        next_row = db.execute(
            "SELECT id, step_num, title, description FROM plan_steps WHERE project_id = ? AND status = 'pending' ORDER BY step_num LIMIT 1",
            (project_id,),
        ).fetchone()
        if next_row:
            db.execute("UPDATE plan_steps SET status = 'active', updated_at = datetime('now') WHERE id = ?", (next_row[0],))
            db.commit()
            return {"id": next_row[0], "step_num": next_row[1], "title": next_row[2], "description": next_row[3]}
        db.commit()
        return None  # All steps complete


def fail_step(project_id: int, error: str = "", retry: bool = True) -> Optional[dict]:
    """Mark active step as failed. If retry, keep active with error appended. Otherwise advance."""
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT id, retry_count FROM plan_steps WHERE project_id = ? AND status = 'active' ORDER BY step_num LIMIT 1",
            (project_id,),
        ).fetchone()
        if not row:
            return None
        step_id, retry_count = row[0], row[1]

        if retry and retry_count < 2:  # Allow up to 3 attempts (0, 1, 2)
            new_count = retry_count + 1
            error_entry = f"\n[ATTEMPT {new_count} FAILED]: {error}"
            db.execute(
                "UPDATE plan_steps SET retry_count = ?, error = error || ?, updated_at = datetime('now') WHERE id = ?",
                (new_count, error_entry, step_id),
            )
            # Return same step (stays active)
            updated = db.execute(
                "SELECT id, step_num, title, description, retry_count, error FROM plan_steps WHERE id = ?",
                (step_id,),
            ).fetchone()
            db.commit()
            return {"id": updated[0], "step_num": updated[1], "title": updated[2],
                    "description": updated[3], "retry_count": updated[4], "error": updated[5]}
        else:
            # Max retries or no retry — mark failed, advance
            error_entry = f"\n[ATTEMPT {retry_count + 1} FAILED]: {error}" if retry else f"\n[FAILED]: {error}"
            db.execute(
                "UPDATE plan_steps SET status = 'failed', error = error || ?, updated_at = datetime('now') WHERE id = ?",
                (error_entry, step_id),
            )
            # Find next pending step
            next_row = db.execute(
                "SELECT id, step_num, title, description FROM plan_steps WHERE project_id = ? AND status = 'pending' ORDER BY step_num LIMIT 1",
                (project_id,),
            ).fetchone()
            if next_row:
                db.execute("UPDATE plan_steps SET status = 'active', updated_at = datetime('now') WHERE id = ?", (next_row[0],))
                db.commit()
                return {"id": next_row[0], "step_num": next_row[1], "title": next_row[2], "description": next_row[3]}
            db.commit()
            return None  # All steps done (some failed)


def get_plan_summary(project_id: int) -> dict:
    """Get summary of all plan steps for a project."""
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT step_num, title, status, retry_count, result, error FROM plan_steps WHERE project_id = ? ORDER BY step_num",
            (project_id,),
        ).fetchall()
        if not rows:
            return {"plan": None}
        plan_name = db.execute(
            "SELECT plan_name FROM plan_steps WHERE project_id = ? LIMIT 1", (project_id,)
        ).fetchone()
        steps = [{"step_num": r[0], "title": r[1], "status": r[2], "retry_count": r[3],
                  "result": r[4], "error": r[5]} for r in rows]
        done = sum(1 for s in steps if s["status"] == "done")
        failed = sum(1 for s in steps if s["status"] == "failed")
        active = sum(1 for s in steps if s["status"] == "active")
        return {
            "plan_name": plan_name[0] if plan_name else "",
            "total": len(steps), "done": done, "failed": failed, "active": active,
            "steps": steps,
        }


def set_project_context(project_id: int, **kwargs) -> str:
    """Set project build context fields. Updates only provided fields."""
    import json as _json
    with sqlite3.connect(DB_PATH) as db:
        proj = db.execute("SELECT context FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not proj:
            return "Error: Project not found"
        ctx = _json.loads(proj[0]) if proj[0] else {}
        ctx.update({k: v for k, v in kwargs.items() if v})
        db.execute("UPDATE projects SET context = ? WHERE id = ?", (_json.dumps(ctx), project_id))
        db.commit()
        return f"Project context updated: {ctx}"


def get_project_context(project_id: int) -> Optional[dict]:
    """Get project build context."""
    import json as _json
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT context FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row and row[0]:
            return _json.loads(row[0])
    return None
