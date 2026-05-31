"""Sloth Engine — authentication."""

from __future__ import annotations

import sqlite3
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import ADMIN_TOKEN, DB_PATH

security = HTTPBearer(auto_error=False)


def _hash_token(email: str, token: str) -> str:
    return bcrypt.hashpw(
        f"{email}:{token}".encode(),
        bcrypt.gensalt(rounds=12),
    ).decode()


def _check_token(email: str, token: str, token_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            f"{email}:{token}".encode(),
            token_hash.encode(),
        )
    except (ValueError, TypeError):
        return False


def init_auth_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA busy_timeout = 5000")
        db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                token_hash TEXT NOT NULL,
                display_name TEXT DEFAULT ''
            )"""
        )
        db.commit()


def create_user(email: str, token: str, display_name: str = "") -> str:
    """Create user, return their API token for one-time display."""
    token_hash = _hash_token(email, token)
    try:
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "INSERT INTO users (email, token_hash, display_name) VALUES (?, ?, ?)",
                (email, token_hash, display_name),
            )
            db.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"User {email} already exists")
    return token


def verify_token(token: str, email: Optional[str] = None) -> Optional[str]:
    """Verify API token, return email or None."""
    with sqlite3.connect(DB_PATH) as db:
        if email:
            row = db.execute(
                "SELECT token_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
            if row and _check_token(email, token, row[0]):
                return email
        else:
            for row in db.execute("SELECT email, token_hash FROM users").fetchall():
                if _check_token(row[0], token, row[1]):
                    return row[0]
        return None


def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """FastAPI dependency — extract user from Bearer token."""
    # Check admin bypass
    if ADMIN_TOKEN and creds and creds.credentials == ADMIN_TOKEN:
        return "admin"

    if not creds:
        raise HTTPException(status_code=401, detail="Missing authorization")

    email = verify_token(creds.credentials)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")
    return email
