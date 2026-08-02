"""
Magic.fm - Autoplay library, listener requests, and the request queue.

Two routers: `router` is public/DJ-facing (library search, requests, status,
forcing the next track), `admin_router` is the loopback-only library CRUD
surface admin.html drives (imports require_admin from admin.py - one-way
dependency, admin.py never imports from here).
"""

import logging
import random
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import db
from nowplaying import require_dj
from admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter()

# Sources considered pre-cleared for 24/7 broadcast. Anything else (currently
# just youtube) is flagged as unlicensed fallback-only in the admin UI.
UNLICENSED_SOURCES = {"youtube"}


# ============================================================================
# Models
# ============================================================================

class RequestTrackRequest(BaseModel):
    library_id: int
    requested_by: Optional[str] = Field(None, max_length=32)


class AddTrackRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    artist: Optional[str] = Field(None, max_length=200)
    source: str = Field(..., min_length=1, max_length=50)
    source_url: Optional[str] = Field(None, max_length=500)
    license_note: Optional[str] = Field(None, max_length=500)


# ============================================================================
# Public / DJ
# ============================================================================

@router.get("/api/autoplay/status")
async def autoplay_status():
    total = db.execute_one("SELECT COUNT(*) FROM autoplay_library")[0]
    licensed = db.execute_one(
        "SELECT COUNT(*) FROM autoplay_library WHERE source NOT IN ({})".format(
            ",".join("?" * len(UNLICENSED_SOURCES))
        ),
        tuple(UNLICENSED_SOURCES),
    )[0]
    queue_length = db.execute_one("SELECT COUNT(*) FROM autoplay_queue")[0]
    nobody_live = db.execute_one("SELECT COUNT(*) FROM live_streams")[0] == 0

    return {
        "autoplay_active": nobody_live and total > 0,
        "library_total": total,
        "library_licensed": licensed,
        "library_unlicensed": total - licensed,
        "queue_length": queue_length,
    }


@router.get("/api/autoplay/queue")
async def get_queue(limit: int = 50):
    limit = max(1, min(limit, 200))
    rows = db.execute_query(
        "SELECT id, title, artist, requested_by FROM autoplay_queue ORDER BY created_at ASC LIMIT ?",
        (limit,),
    )
    return [{"queue_id": r[0], "title": r[1], "artist": r[2], "requested_by": r[3]} for r in rows]


@router.get("/api/autoplay/search")
async def search_library(q: str = "", limit: int = 12):
    limit = max(1, min(limit, 50))
    like = f"%{q}%"
    rows = db.execute_query(
        """
        SELECT id, title, artist FROM autoplay_library
        WHERE is_enabled = 1 AND (title LIKE ? OR artist LIKE ?)
        ORDER BY title ASC LIMIT ?
        """,
        (like, like, limit),
    )
    return [{"library_id": r[0], "title": r[1], "artist": r[2]} for r in rows]


@router.post("/api/autoplay/request")
async def request_track(data: RequestTrackRequest):
    track = db.execute_one(
        "SELECT title, artist FROM autoplay_library WHERE id = ? AND is_enabled = 1",
        (data.library_id,),
    )
    if not track:
        raise HTTPException(status_code=404, detail="Track not found or not available")

    requested_by = (data.requested_by or "").strip() or "Anonymous"

    db.execute_update(
        "INSERT INTO autoplay_queue (library_id, title, artist, requested_by) VALUES (?, ?, ?, ?)",
        (data.library_id, track[0], track[1], requested_by),
    )
    position = db.execute_one("SELECT COUNT(*) FROM autoplay_queue")[0]

    return {"title": track[0], "artist": track[1], "position": position}


@router.post("/api/autoplay/next")
async def advance_track(dj: Dict = Depends(require_dj)):
    queued = db.execute_one(
        """
        SELECT q.id, q.library_id, q.title, q.artist, q.requested_by, l.source
        FROM autoplay_queue q JOIN autoplay_library l ON l.id = q.library_id
        ORDER BY q.created_at ASC LIMIT 1
        """
    )
    if queued:
        queue_id, library_id, title, artist, requested_by, source = queued
        db.execute_update("DELETE FROM autoplay_queue WHERE id = ?", (queue_id,))
        db.execute_update(
            "UPDATE autoplay_library SET play_count = play_count + 1 WHERE id = ?", (library_id,)
        )
        return {"title": title, "artist": artist, "source": source, "requested_by": requested_by}

    candidates = db.execute_query(
        "SELECT id, title, artist, source FROM autoplay_library WHERE is_enabled = 1"
    )
    if not candidates:
        raise HTTPException(status_code=404, detail="Autoplay library is empty")

    library_id, title, artist, source = random.choice(candidates)
    db.execute_update(
        "UPDATE autoplay_library SET play_count = play_count + 1 WHERE id = ?", (library_id,)
    )
    return {"title": title, "artist": artist, "source": source, "requested_by": None}


# ============================================================================
# Admin (loopback-only, via require_admin)
# ============================================================================

@admin_router.get("/api/admin/autoplay/library")
async def list_library(limit: int = 100, admin: Dict = Depends(require_admin)):
    limit = max(1, min(limit, 500))
    rows = db.execute_query(
        """
        SELECT id, title, artist, source, license_note, is_enabled, play_count
        FROM autoplay_library ORDER BY created_at DESC LIMIT ?
        """,
        (limit,),
    )
    return [
        {
            "library_id": r[0], "title": r[1], "artist": r[2], "source": r[3],
            "license_note": r[4], "is_enabled": bool(r[5]), "play_count": r[6],
        }
        for r in rows
    ]


@admin_router.post("/api/admin/autoplay/library")
async def add_track(data: AddTrackRequest, admin: Dict = Depends(require_admin)):
    library_id = db.execute_update(
        """
        INSERT INTO autoplay_library (title, artist, source, source_url, license_note, is_enabled)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (data.title, data.artist, data.source, data.source_url, data.license_note),
    )
    return {"library_id": library_id, "status": "ok"}


@admin_router.post("/api/admin/autoplay/library/{library_id}/toggle")
async def toggle_track(library_id: int, admin: Dict = Depends(require_admin)):
    row = db.execute_one("SELECT is_enabled FROM autoplay_library WHERE id = ?", (library_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Track not found")
    db.execute_update(
        "UPDATE autoplay_library SET is_enabled = ? WHERE id = ?", (0 if row[0] else 1, library_id)
    )
    return {"status": "ok", "is_enabled": not bool(row[0])}


@admin_router.delete("/api/admin/autoplay/library/{library_id}")
async def delete_track(library_id: int, admin: Dict = Depends(require_admin)):
    if not db.execute_one("SELECT id FROM autoplay_library WHERE id = ?", (library_id,)):
        raise HTTPException(status_code=404, detail="Track not found")
    # Drop any pending requests for this track first so the public queue
    # never shows a dangling library_id.
    db.execute_update("DELETE FROM autoplay_queue WHERE library_id = ?", (library_id,))
    db.execute_update("DELETE FROM autoplay_library WHERE id = ?", (library_id,))
    return {"status": "deleted"}


@admin_router.delete("/api/admin/autoplay/queue/{queue_id}")
async def remove_queued(queue_id: int, admin: Dict = Depends(require_admin)):
    if not db.execute_one("SELECT id FROM autoplay_queue WHERE id = ?", (queue_id,)):
        raise HTTPException(status_code=404, detail="Queue entry not found")
    db.execute_update("DELETE FROM autoplay_queue WHERE id = ?", (queue_id,))
    return {"status": "deleted"}
