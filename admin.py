"""
Magic.fm - Admin Module

Account creation is admin-only. There is no public sign-up.

WHY OPEN REGISTRATION WAS REMOVED
---------------------------------
The original build exposed POST /api/auth/register with no gate. Anyone who found
the login page could create an account and immediately receive a working stream key.
For a platform whose entire model is "the owner interviews and vets every DJ", that
is a broadcast-access hole, not a convenience feature.

Registration is now disabled by default and controlled by ALLOW_OPEN_REGISTRATION.
Leave it off. It exists only so a future public-signup mode does not require a code
change.

LOCAL-ONLY ADMIN ACCESS
------------------------
require_admin() now also requires the request to arrive from loopback
(127.0.0.1 / ::1). Paired with the nginx block in ADMIN-ACCESS.md that also
restricts /admin.html and /api/admin/* to loopback, the only way to reach
admin at all is an SSH tunnel into the VPS - see ADMIN-ACCESS.md for the
client-side steps. This is a second, app-level check in case nginx is ever
misconfigured or bypassed.
"""

import os
import logging
from typing import Optional, Dict, List
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr, field_validator

from database import db
from security import PasswordManager, AuditLogger, validate_password_strength
from middleware import get_client_ip
from nowplaying import require_dj

logger = logging.getLogger(__name__)

router = APIRouter()

# Off by default. This is the safe default and should stay off.
ALLOW_OPEN_REGISTRATION = os.getenv("ALLOW_OPEN_REGISTRATION", "false").lower() == "true"

# Admin is only reachable via an SSH tunnel (see ADMIN-ACCESS.md). This is the
# app-level half of that gate; nginx enforces the same restriction in front of it.
LOOPBACK_IPS = {"127.0.0.1", "::1"}


# ============================================================================
# Admin dependency
# ============================================================================

async def require_admin(request: Request, dj: Dict = Depends(require_dj)) -> Dict:
    """
    Require the caller to be an admin, AND to be calling from loopback.

    Re-reads is_admin from the database on every request rather than trusting a
    claim inside the JWT. If admin rights were baked into the token, revoking them
    would not take effect until the token expired - up to 24 hours of continued
    admin access after you removed someone. Reading live means revocation is
    immediate.

    The loopback check means admin is unreachable from the open internet even
    with valid credentials - it can only be reached through the SSH tunnel
    described in ADMIN-ACCESS.md. nginx already blocks the same paths for
    anyone not on loopback; this is the belt-and-suspenders app-level copy of
    that check, in case nginx is ever misconfigured or bypassed.
    """
    client_ip = await get_client_ip(request)
    if client_ip not in LOOPBACK_IPS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin is only reachable through the SSH tunnel."
        )

    row = db.execute_one(
        "SELECT is_admin, is_active FROM djs WHERE id = ?", (dj["dj_id"],)
    )
    if not row or not row[0] or not row[1]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return dj


# ============================================================================
# Models
# ============================================================================

class CreateDJRequest(BaseModel):
    """Admin creates a DJ account with a username and password they choose."""
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)
    must_change_password: bool = True

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


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)
    must_change_password: bool = True

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        ok, msg = validate_password_strength(v)
        if not ok:
            raise ValueError(msg)
        return v


class ChangeOwnPasswordRequest(BaseModel):
    """A DJ changing their own password. Requires the current one."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        ok, msg = validate_password_strength(v)
        if not ok:
            raise ValueError(msg)
        return v


class UpdateNotesRequest(BaseModel):
    notes: str = Field(default="", max_length=2000)


class DJSummary(BaseModel):
    dj_id: int
    username: str
    email: str
    display_name: Optional[str]
    is_active: bool
    is_admin: bool
    must_change_password: bool
    created_at: Optional[str]
    last_login: Optional[str]
    stream_key_count: int
    notes: Optional[str]


# ============================================================================
# Account management
# ============================================================================

@router.post("/api/admin/djs")
async def create_dj(request: Request, data: CreateDJRequest,
                    admin: Dict = Depends(require_admin)):
    """
    Create a DJ account. Admin only.

    This is the only way an account comes into existence. The admin picks the
    initial username and password and hands them to the DJ directly.

    must_change_password defaults to True so the admin-chosen password is replaced
    by one only the DJ knows. Without that, you would permanently know every DJ's
    password, which is bad for them and bad for you.
    """
    client_ip = await get_client_ip(request)

    existing = db.execute_one(
        "SELECT id FROM djs WHERE username = ? OR email = ?",
        (data.username, data.email)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already in use")

    password_hash = PasswordManager.hash_password(data.password)

    dj_id = db.execute_update(
        """
        INSERT INTO djs
            (username, email, password_hash, display_name, is_active, is_admin,
             created_by, notes, must_change_password)
        VALUES (?, ?, ?, ?, 1, 0, ?, ?, ?)
        """,
        (data.username, data.email, password_hash, data.display_name,
         admin["dj_id"], data.notes, 1 if data.must_change_password else 0)
    )

    # Issue a stream key immediately so the DJ can be handed working credentials.
    from security import StreamKeyManager
    stream_key = StreamKeyManager.create_key_for_dj(dj_id)

    AuditLogger.log_event(
        admin["dj_id"], "ADMIN_CREATED_DJ",
        f"created dj_id={dj_id} username={data.username}", client_ip
    )

    return {
        "dj_id": dj_id,
        "username": data.username,
        "stream_key": stream_key,
        "must_change_password": data.must_change_password,
        "note": "Give the DJ their username, password and stream key. "
                "They will be asked to set a new password on first login.",
    }


@router.get("/api/admin/djs")
async def list_djs(admin: Dict = Depends(require_admin)) -> List[dict]:
    """List all accounts with status. Admin only."""
    rows = db.execute_query(
        """
        SELECT d.id, d.username, d.email, d.display_name, d.is_active, d.is_admin,
               d.must_change_password, d.created_at, d.last_login, d.notes,
               (SELECT COUNT(*) FROM stream_keys sk
                WHERE sk.dj_id = d.id AND sk.is_active = 1) AS key_count
        FROM djs d
        ORDER BY d.is_admin DESC, d.username
        """
    )
    return [
        {
            "dj_id": r[0], "username": r[1], "email": r[2], "display_name": r[3],
            "is_active": bool(r[4]), "is_admin": bool(r[5]),
            "must_change_password": bool(r[6]), "created_at": r[7],
            "last_login": r[8], "notes": r[9], "stream_key_count": r[10],
        }
        for r in rows
    ]


@router.post("/api/admin/djs/{dj_id}/suspend")
async def suspend_dj(dj_id: int, request: Request, admin: Dict = Depends(require_admin)):
    """
    Suspend an account.

    Sets is_active = 0, which cascades everywhere it matters: login is refused,
    stream key validation fails (so an in-progress broadcast is cut at the next
    publish attempt), and metadata token validation fails. One switch, total
    revocation - which is what you want when someone has to go mid-set.
    """
    client_ip = await get_client_ip(request)

    if dj_id == admin["dj_id"]:
        raise HTTPException(status_code=400, detail="You cannot suspend your own account")

    target = db.execute_one("SELECT username, is_admin FROM djs WHERE id = ?", (dj_id,))
    if not target:
        raise HTTPException(status_code=404, detail="Account not found")

    # Refuse to leave the platform with no working admin.
    if target[1]:
        remaining = db.execute_one(
            "SELECT COUNT(*) FROM djs WHERE is_admin = 1 AND is_active = 1 AND id != ?",
            (dj_id,)
        )[0]
        if remaining == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot suspend the last active admin account"
            )

    db.execute_update("UPDATE djs SET is_active = 0 WHERE id = ?", (dj_id,))
    db.execute_update("UPDATE stream_keys SET is_active = 0 WHERE dj_id = ?", (dj_id,))
    db.execute_update("UPDATE metadata_tokens SET is_active = 0 WHERE dj_id = ?", (dj_id,))
    db.execute_update("DELETE FROM nowplaying WHERE dj_id = ?", (dj_id,))

    AuditLogger.log_event(admin["dj_id"], "ADMIN_SUSPENDED_DJ",
                          f"dj_id={dj_id} username={target[0]}", client_ip)

    return {"status": "suspended", "dj_id": dj_id,
            "note": "Login, stream keys and metadata tokens all revoked."}


@router.post("/api/admin/djs/{dj_id}/reactivate")
async def reactivate_dj(dj_id: int, request: Request, admin: Dict = Depends(require_admin)):
    """
    Reactivate a suspended account.

    Deliberately does NOT restore old stream keys. If an account was suspended
    because a key leaked, silently re-enabling that key would reopen the hole.
    A fresh key is issued instead.
    """
    client_ip = await get_client_ip(request)

    target = db.execute_one("SELECT username FROM djs WHERE id = ?", (dj_id,))
    if not target:
        raise HTTPException(status_code=404, detail="Account not found")

    db.execute_update("UPDATE djs SET is_active = 1 WHERE id = ?", (dj_id,))

    from security import StreamKeyManager
    stream_key = StreamKeyManager.create_key_for_dj(dj_id)

    AuditLogger.log_event(admin["dj_id"], "ADMIN_REACTIVATED_DJ",
                          f"dj_id={dj_id} username={target[0]}", client_ip)

    return {"status": "reactivated", "dj_id": dj_id, "new_stream_key": stream_key,
            "note": "A new stream key was issued. Old keys stay revoked."}


@router.post("/api/admin/djs/{dj_id}/reset-password")
async def reset_password(dj_id: int, data: ResetPasswordRequest, request: Request,
                         admin: Dict = Depends(require_admin)):
    """Set a new password for a DJ. Admin only."""
    client_ip = await get_client_ip(request)

    target = db.execute_one("SELECT username FROM djs WHERE id = ?", (dj_id,))
    if not target:
        raise HTTPException(status_code=404, detail="Account not found")

    db.execute_update(
        "UPDATE djs SET password_hash = ?, must_change_password = ? WHERE id = ?",
        (PasswordManager.hash_password(data.new_password),
         1 if data.must_change_password else 0, dj_id)
    )

    AuditLogger.log_event(admin["dj_id"], "ADMIN_RESET_PASSWORD",
                          f"dj_id={dj_id} username={target[0]}", client_ip)

    return {"status": "password reset", "dj_id": dj_id}


@router.put("/api/admin/djs/{dj_id}/notes")
async def update_notes(dj_id: int, data: UpdateNotesRequest,
                       admin: Dict = Depends(require_admin)):
    """
    Update private admin notes on a DJ.

    Never exposed on any public or DJ-facing endpoint - admin eyes only.
    """
    if not db.execute_one("SELECT id FROM djs WHERE id = ?", (dj_id,)):
        raise HTTPException(status_code=404, detail="Account not found")

    db.execute_update("UPDATE djs SET notes = ? WHERE id = ?", (data.notes, dj_id))
    return {"status": "ok"}


@router.post("/api/admin/djs/{dj_id}/revoke-keys")
async def revoke_keys(dj_id: int, request: Request, admin: Dict = Depends(require_admin)):
    """
    Revoke all stream keys for a DJ and issue a fresh one.

    The panic button for a leaked key. Takes effect on the next RTMP publish.
    """
    client_ip = await get_client_ip(request)

    if not db.execute_one("SELECT id FROM djs WHERE id = ?", (dj_id,)):
        raise HTTPException(status_code=404, detail="Account not found")

    db.execute_update("UPDATE stream_keys SET is_active = 0 WHERE dj_id = ?", (dj_id,))

    from security import StreamKeyManager
    new_key = StreamKeyManager.create_key_for_dj(dj_id)

    AuditLogger.log_event(admin["dj_id"], "ADMIN_REVOKED_KEYS",
                          f"dj_id={dj_id}", client_ip)

    return {"status": "keys revoked", "new_stream_key": new_key}


@router.get("/api/admin/audit-log")
async def get_audit_log(limit: int = 100, admin: Dict = Depends(require_admin)):
    """Recent audit events. Admin only."""
    limit = max(1, min(limit, 500))
    rows = db.execute_query(
        """
        SELECT a.timestamp, a.action, a.details, a.ip_address,
               COALESCE(d.username, '-') AS username
        FROM audit_log a
        LEFT JOIN djs d ON a.dj_id = d.id
        ORDER BY a.timestamp DESC
        LIMIT ?
        """,
        (limit,)
    )
    return [
        {"timestamp": r[0], "action": r[1], "details": r[2],
         "ip_address": r[3], "username": r[4]}
        for r in rows
    ]


# ============================================================================
# DJ self-service
# ============================================================================

@router.post("/api/dj/change-password")
async def change_own_password(data: ChangeOwnPasswordRequest, request: Request,
                              dj: Dict = Depends(require_dj)):
    """
    A DJ changes their own password.

    Requires the current password even though the session is already authenticated.
    That way a hijacked session alone is not enough to lock the real owner out.
    """
    client_ip = await get_client_ip(request)

    row = db.execute_one("SELECT password_hash FROM djs WHERE id = ?", (dj["dj_id"],))
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")

    if not PasswordManager.verify_password(data.current_password, row[0]):
        AuditLogger.log_event(dj["dj_id"], "PASSWORD_CHANGE_FAILED",
                              "wrong current password", client_ip)
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    db.execute_update(
        "UPDATE djs SET password_hash = ?, must_change_password = 0 WHERE id = ?",
        (PasswordManager.hash_password(data.new_password), dj["dj_id"])
    )

    AuditLogger.log_event(dj["dj_id"], "PASSWORD_CHANGED", ip_address=client_ip)
    return {"status": "password changed"}


@router.get("/api/dj/me")
async def get_own_profile(dj: Dict = Depends(require_dj)):
    """
    The authenticated DJ's own profile.

    Note this deliberately does NOT return the `notes` column - those are private
    admin vetting notes and must never be readable by the DJ they describe.
    """
    row = db.execute_one(
        """
        SELECT id, username, email, display_name, is_active, is_admin,
               must_change_password, created_at, last_login
        FROM djs WHERE id = ?
        """,
        (dj["dj_id"],)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")

    return {
        "dj_id": row[0], "username": row[1], "email": row[2], "display_name": row[3],
        "is_active": bool(row[4]), "is_admin": bool(row[5]),
        "must_change_password": bool(row[6]), "created_at": row[7], "last_login": row[8],
    }
