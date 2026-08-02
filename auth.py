"""
Magic.fm - Login, (gated) registration, stream keys, DJ dashboard.

Registration is off by default - see admin.py's module docstring for why.
ALLOW_OPEN_REGISTRATION here uses the exact same env var and default as
admin.py so the two can never disagree about whether signup is open.
"""

import os
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator

from database import db
from security import (
    AuditLogger,
    PasswordManager,
    StreamKeyManager,
    TokenManager,
    validate_password_strength,
)
from middleware import get_client_ip
from nowplaying import require_dj
from stream import get_live_stream_for_dj, _rtmp_stats_for

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOW_OPEN_REGISTRATION = os.getenv("ALLOW_OPEN_REGISTRATION", "false").lower() == "true"


# ============================================================================
# Models
# ============================================================================

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=32)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=100)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        v = v.strip().lower()
        if not all(c.isalnum() or c == '_' for c in v):
            raise ValueError('Username: letters, numbers and underscores only')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        ok, msg = validate_password_strength(v)
        if not ok:
            raise ValueError(msg)
        return v


# ============================================================================
# Login / register
# ============================================================================

@router.post("/api/auth/login")
async def login(data: LoginRequest, request: Request):
    client_ip = await get_client_ip(request)
    username = data.username.strip().lower()

    row = db.execute_one(
        "SELECT id, password_hash, is_active FROM djs WHERE username = ?", (username,)
    )
    if not row or not PasswordManager.verify_password(data.password, row[1]):
        AuditLogger.log_event(row[0] if row else None, "LOGIN_FAILED", username, client_ip)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    dj_id, _, is_active = row
    if not is_active:
        AuditLogger.log_event(dj_id, "LOGIN_REJECTED_SUSPENDED", username, client_ip)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    db.execute_update("UPDATE djs SET last_login = datetime('now') WHERE id = ?", (dj_id,))
    AuditLogger.log_event(dj_id, "LOGIN_SUCCESS", None, client_ip)

    token = TokenManager.create_access_token(dj_id, username)
    return {"access_token": token, "token_type": "bearer", "username": username}


@router.post("/api/auth/register")
async def register(data: RegisterRequest, request: Request):
    if not ALLOW_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Registration is disabled. Accounts are set up by the station owner.",
        )

    client_ip = await get_client_ip(request)

    existing = db.execute_one(
        "SELECT id FROM djs WHERE username = ? OR email = ?", (data.username, data.email)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already in use")

    password_hash = PasswordManager.hash_password(data.password)
    dj_id = db.execute_update(
        """
        INSERT INTO djs
            (username, email, password_hash, display_name, is_active, is_admin,
             created_by, notes, must_change_password)
        VALUES (?, ?, ?, ?, 1, 0, NULL, NULL, 0)
        """,
        (data.username, data.email, password_hash, data.display_name),
    )
    StreamKeyManager.create_key_for_dj(dj_id)

    AuditLogger.log_event(dj_id, "SELF_REGISTERED", f"username={data.username}", client_ip)

    token = TokenManager.create_access_token(dj_id, data.username)
    return {"access_token": token, "token_type": "bearer", "username": data.username}


# ============================================================================
# Stream keys
# ============================================================================

@router.get("/api/auth/stream-key")
async def list_stream_keys(dj: Dict = Depends(require_dj)):
    return StreamKeyManager.list_keys_for_dj(dj["dj_id"])


@router.post("/api/auth/stream-key")
async def create_stream_key(request: Request, dj: Dict = Depends(require_dj)):
    client_ip = await get_client_ip(request)
    stream_key = StreamKeyManager.create_key_for_dj(dj["dj_id"])
    AuditLogger.log_event(dj["dj_id"], "STREAM_KEY_GENERATED", None, client_ip)
    return {"status": "ok", "stream_key": stream_key}


# ============================================================================
# Dashboard
# ============================================================================

@router.get("/api/dj/dashboard")
async def get_dashboard(dj: Dict = Depends(require_dj)):
    row = db.execute_one(
        """
        SELECT id, username, email, display_name, is_active, is_admin,
               must_change_password, created_at, last_login
        FROM djs WHERE id = ?
        """,
        (dj["dj_id"],),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")

    profile = {
        "dj_id": row[0], "username": row[1], "email": row[2], "display_name": row[3],
        "is_active": bool(row[4]), "is_admin": bool(row[5]),
        "must_change_password": bool(row[6]), "created_at": row[7], "last_login": row[8],
    }

    stream_name = get_live_stream_for_dj(dj["dj_id"])
    is_live = stream_name is not None
    viewers = _rtmp_stats_for(stream_name).get("viewers") if stream_name else None

    show_rows = db.execute_query(
        """
        SELECT show_name, start_time, end_time, description
        FROM shows
        WHERE dj_id = ? AND end_time > strftime('%Y-%m-%dT%H:%M:%S', 'now')
        ORDER BY start_time ASC LIMIT 20
        """,
        (dj["dj_id"],),
    )
    upcoming_shows = [
        {
            "show_name": r[0],
            "start_time": r[1] + ("Z" if not r[1].endswith("Z") else ""),
            "end_time": r[2] + ("Z" if not r[2].endswith("Z") else ""),
            "description": r[3],
        }
        for r in show_rows
    ]

    return {
        "profile": profile,
        "current_stream_status": {"is_live": is_live, "viewers": viewers},
        "stream_keys": StreamKeyManager.list_keys_for_dj(dj["dj_id"]),
        "upcoming_shows": upcoming_shows,
    }
