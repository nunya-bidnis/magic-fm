"""
Magic.fm - Security primitives

Passwords: bcrypt via the `bcrypt` package directly (no passlib dependency).
Sessions: JWT (HS256), secret from JWT_SECRET env var - never hardcoded.
Stream keys / metadata tokens: secrets.token_urlsafe, stored in plaintext in
their own narrow-purpose tables so they can be listed back to the owning DJ
and revoked (regenerable, per the project's security requirements - these
are bearer credentials for RTMP/agent auth, not login passwords).
"""

import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt

from database import db

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not set. Generate one with `openssl rand -hex 32` and "
        "put it in .env - see .env.example."
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))


# ============================================================================
# Passwords
# ============================================================================

class PasswordManager:
    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Matches the rule shown on every form in the frontend: 8+ chars, 1 uppercase, 1 digit."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    return True, ""


# ============================================================================
# JWT session tokens
# ============================================================================

class TokenManager:
    @staticmethod
    def create_access_token(dj_id: int, username: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(dj_id),
            "username": username,
            "iat": now,
            "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_access_token(token: str) -> Optional[dict]:
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.PyJWTError:
            return None


# ============================================================================
# Stream keys (RTMP broadcast credentials)
# ============================================================================

class StreamKeyManager:
    @staticmethod
    def create_key_for_dj(dj_id: int) -> str:
        key = "mfm_" + secrets.token_urlsafe(24)
        db.execute_update(
            "INSERT INTO stream_keys (dj_id, stream_key, is_active) VALUES (?, ?, 1)",
            (dj_id, key),
        )
        return key

    @staticmethod
    def list_keys_for_dj(dj_id: int) -> list:
        rows = db.execute_query(
            """
            SELECT stream_key, created_at, last_used
            FROM stream_keys WHERE dj_id = ? AND is_active = 1
            ORDER BY created_at DESC
            """,
            (dj_id,),
        )
        return [{"stream_key": r[0], "created_at": r[1], "last_used": r[2]} for r in rows]

    @staticmethod
    def validate_key(stream_key: str) -> Optional[int]:
        """Returns dj_id if the key is active and its owner is active, else None."""
        row = db.execute_one(
            """
            SELECT sk.dj_id FROM stream_keys sk
            JOIN djs d ON d.id = sk.dj_id
            WHERE sk.stream_key = ? AND sk.is_active = 1 AND d.is_active = 1
            """,
            (stream_key,),
        )
        if not row:
            return None
        db.execute_update(
            "UPDATE stream_keys SET last_used = datetime('now') WHERE stream_key = ?",
            (stream_key,),
        )
        return row[0]


# ============================================================================
# Metadata tokens (Now Playing agent auth - NOT the stream key)
# ============================================================================

class MetadataTokenManager:
    @staticmethod
    def get_or_create_for_dj(dj_id: int) -> str:
        row = db.execute_one(
            "SELECT token FROM metadata_tokens WHERE dj_id = ? AND is_active = 1",
            (dj_id,),
        )
        if row:
            return row[0]
        token = "npt_" + secrets.token_urlsafe(24)
        db.execute_update(
            "INSERT INTO metadata_tokens (dj_id, token, is_active) VALUES (?, ?, 1)",
            (dj_id, token),
        )
        return token

    @staticmethod
    def rotate_for_dj(dj_id: int) -> str:
        db.execute_update(
            "UPDATE metadata_tokens SET is_active = 0 WHERE dj_id = ?", (dj_id,)
        )
        token = "npt_" + secrets.token_urlsafe(24)
        db.execute_update(
            "INSERT INTO metadata_tokens (dj_id, token, is_active) VALUES (?, ?, 1)",
            (dj_id, token),
        )
        return token

    @staticmethod
    def validate_token(token: str) -> Optional[int]:
        """Returns dj_id if the token is active and its owner is active, else None."""
        row = db.execute_one(
            """
            SELECT mt.dj_id FROM metadata_tokens mt
            JOIN djs d ON d.id = mt.dj_id
            WHERE mt.token = ? AND mt.is_active = 1 AND d.is_active = 1
            """,
            (token,),
        )
        return row[0] if row else None


# ============================================================================
# Audit log
# ============================================================================

class AuditLogger:
    @staticmethod
    def log_event(dj_id: Optional[int], action: str, details: Optional[str] = None,
                   ip_address: Optional[str] = None) -> None:
        db.execute_update(
            "INSERT INTO audit_log (dj_id, action, details, ip_address) VALUES (?, ?, ?, ?)",
            (dj_id, action, details, ip_address),
        )
