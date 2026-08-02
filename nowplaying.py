"""
Magic.fm - Now Playing ticker + DJ session auth.

Houses require_dj because it's the one dependency almost every other module
needs (admin.py, auth.py, schedule.py, autoplay.py all import it), and it
naturally belongs next to the other now-playing/session primitives it's
built from.

Two separate credential types are in play here, on purpose:
- The JWT (Authorization: Bearer, from /api/auth/login) is a DJ's login
  session - manual ticker edits and clearing it require this.
- The metadata token (X-Metadata-Token) is a narrower, separately-revocable
  credential handed to a Now Playing agent. It can only push/read track
  info - it cannot log in anywhere, see the dashboard, or touch stream keys.
  That way a compromised agent config leaks a lot less than a compromised
  password would.
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from database import db
from security import MetadataTokenManager, TokenManager

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Session dependency
# ============================================================================

async def require_dj(request: Request) -> Dict:
    """Require a valid DJ session JWT. Re-checks is_active on every call."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    payload = TokenManager.decode_access_token(auth[7:].strip())
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        dj_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token")

    row = db.execute_one("SELECT id, username, is_active FROM djs WHERE id = ?", (dj_id,))
    if not row or not row[2]:
        raise HTTPException(status_code=401, detail="Account not found or inactive")

    return {"dj_id": row[0], "username": row[1]}


async def require_metadata_token(x_metadata_token: Optional[str] = Header(default=None)) -> int:
    """Require a valid, active metadata token. Returns the owning dj_id."""
    if not x_metadata_token:
        raise HTTPException(status_code=401, detail="Missing X-Metadata-Token header")
    dj_id = MetadataTokenManager.validate_token(x_metadata_token)
    if dj_id is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked metadata token")
    return dj_id


# ============================================================================
# Public now playing
# ============================================================================

@router.get("/api/nowplaying")
async def get_nowplaying():
    """Whatever is most recently updated across all DJs. Idle if nobody's posted anything."""
    row = db.execute_one(
        """
        SELECT np.track, np.artist, np.art_url, COALESCE(d.display_name, d.username)
        FROM nowplaying np JOIN djs d ON d.id = np.dj_id
        ORDER BY np.updated_at DESC LIMIT 1
        """
    )
    if not row:
        return {"is_live": False, "track": None, "artist": None, "dj": None, "art_url": None}
    return {"is_live": True, "track": row[0], "artist": row[1], "art_url": row[2], "dj": row[3]}


def _upsert_nowplaying(dj_id: int, track: str, artist: Optional[str], art_url: Optional[str]) -> None:
    db.execute_update(
        """
        INSERT INTO nowplaying (dj_id, track, artist, art_url, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(dj_id) DO UPDATE SET
            track = excluded.track,
            artist = excluded.artist,
            art_url = excluded.art_url,
            updated_at = excluded.updated_at
        """,
        (dj_id, track, artist, art_url),
    )


# ============================================================================
# Now Playing agent (metadata token)
# ============================================================================

class AgentNowPlayingRequest(BaseModel):
    track: str = Field(..., min_length=1, max_length=200)
    artist: Optional[str] = Field(None, max_length=200)
    art_url: Optional[str] = Field(None, max_length=500)


@router.post("/api/dj/nowplaying")
async def agent_set_nowplaying(data: AgentNowPlayingRequest, dj_id: int = Depends(require_metadata_token)):
    _upsert_nowplaying(dj_id, data.track, data.artist, data.art_url)
    return {"status": "ok", "track": data.track, "artist": data.artist, "art_url": data.art_url}


@router.get("/api/dj/nowplaying")
async def agent_get_nowplaying(dj_id: int = Depends(require_metadata_token)):
    row = db.execute_one(
        "SELECT track, artist, art_url FROM nowplaying WHERE dj_id = ?", (dj_id,)
    )
    if not row:
        return {"is_live": False, "track": None, "artist": None, "art_url": None}
    return {"is_live": True, "track": row[0], "artist": row[1], "art_url": row[2]}


# ============================================================================
# Manual entry / clear (JWT - the DJ themself, via dj-nowplaying.html)
# ============================================================================

class ManualNowPlayingRequest(BaseModel):
    track: str = Field(..., min_length=1, max_length=200)
    artist: Optional[str] = Field(None, max_length=200)


@router.post("/api/dj/nowplaying/manual")
async def manual_set_nowplaying(data: ManualNowPlayingRequest, dj: Dict = Depends(require_dj)):
    # Manual entry has no artwork source, so any stale art_url from an agent
    # is cleared rather than left showing next to a now-wrong track.
    _upsert_nowplaying(dj["dj_id"], data.track, data.artist, None)
    return {"status": "ok", "track": data.track, "artist": data.artist}


@router.delete("/api/dj/nowplaying")
async def clear_nowplaying(dj: Dict = Depends(require_dj)):
    db.execute_update("DELETE FROM nowplaying WHERE dj_id = ?", (dj["dj_id"],))
    return {"status": "cleared"}


# ============================================================================
# Metadata token issuance (JWT)
# ============================================================================

@router.get("/api/dj/metadata-token")
async def get_metadata_token(dj: Dict = Depends(require_dj)):
    token = MetadataTokenManager.get_or_create_for_dj(dj["dj_id"])
    return {"metadata_token": token}


@router.post("/api/dj/metadata-token")
async def rotate_metadata_token(dj: Dict = Depends(require_dj)):
    token = MetadataTokenManager.rotate_for_dj(dj["dj_id"])
    return {"metadata_token": token}
