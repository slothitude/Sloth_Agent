"""Sloth Engine — authentication."""

from __future__ import annotations

import hashlib
import hmac
import sqlite3
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import API_KEY_SALT, ADMIN_TOKEN, DB_PATH

security = HTTPBearer(auto_error=False)


def _hash_token(email: str, token: str) -> str:
    return hmac.new(
        API_KEY_SALT.encode(),
        f"{email}:{token}".encode(),
        hashlib.sha256,
    ).hexdigest()


def init_auth_db():
    with sqlite3.connect(DB_PATH) as db:
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
        else:
            # Search all users — hash is unique per email:token pair
            for row in db.execute("SELECT email, token_hash FROM users").fetchall():
                if _hash_token(row[0], token) == row[1]:
                    return row[0]
            return None
        if row and row[0] == _hash_token(email, token):
            return email
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
