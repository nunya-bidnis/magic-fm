"""
Magic.fm - RTMP publish auth + live status + DASH manifest routing.

DJs publish straight to nginx-rtmp with their existing stream key as the
RTMP stream name (Server: rtmp://host:1935/live, Stream Key: <their key>,
same key already shown on the dashboard for this exact purpose). nginx-rtmp
calls back into these two endpoints on publish start/stop - they're never
reachable from outside since nginx-rtmp calls them over loopback the same
way uvicorn only listens on 127.0.0.1.

nginx-rtmp's DASH module names manifest/segment files after the stream name
(i.e. the DJ's key), but the frontend hardcodes a single public URL
(/api/stream/dash/manifest.mpd) since only one DJ is ever "on air" at a
time. GET .../manifest.mpd looks up whichever stream is currently live and
redirects to its real manifest file; the actual segment files are served
by a plain static mount right below that route.
"""

import logging
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from database import db
from security import AuditLogger, StreamKeyManager

logger = logging.getLogger(__name__)

router = APIRouter()

DASH_DIR = Path(__file__).resolve().parent / "dash"
DASH_DIR.mkdir(exist_ok=True)

RTMP_STAT_URL = "http://127.0.0.1/rtmp-stat"


# ============================================================================
# nginx-rtmp callbacks (on_publish / on_publish_done)
# ============================================================================

@router.post("/api/stream/auth")
async def stream_auth(request: Request):
    form = await request.form()
    stream_name = form.get("name", "")

    dj_id = StreamKeyManager.validate_key(stream_name)
    if dj_id is None:
        logger.warning("Rejected RTMP publish with unknown/revoked key")
        raise HTTPException(status_code=403, detail="Invalid stream key")

    db.execute_update(
        "INSERT OR REPLACE INTO live_streams (stream_name, dj_id, started_at) "
        "VALUES (?, ?, datetime('now'))",
        (stream_name, dj_id),
    )
    AuditLogger.log_event(dj_id, "STREAM_STARTED", stream_name)
    return {"status": "ok"}


@router.post("/api/stream/publish-done")
async def stream_publish_done(request: Request):
    form = await request.form()
    stream_name = form.get("name", "")

    row = db.execute_one(
        "SELECT dj_id FROM live_streams WHERE stream_name = ?", (stream_name,)
    )
    db.execute_update("DELETE FROM live_streams WHERE stream_name = ?", (stream_name,))
    if row:
        AuditLogger.log_event(row[0], "STREAM_ENDED", stream_name)

    # dash_cleanup only prunes segments *during* a live stream, not after it
    # ends - without this, every past broadcast's fragments sit on disk
    # forever. Stream names are validated stream keys (StreamKeyManager,
    # url-safe tokens), so this glob can't escape the dash directory.
    if stream_name:
        for leftover in DASH_DIR.glob(f"{stream_name}*"):
            leftover.unlink(missing_ok=True)

    return {"status": "ok"}


# ============================================================================
# Public status
# ============================================================================

def get_live_stream_for_dj(dj_id: int) -> Optional[str]:
    """Returns the active stream_name for this dj_id, or None if they're not broadcasting."""
    row = db.execute_one("SELECT stream_name FROM live_streams WHERE dj_id = ?", (dj_id,))
    return row[0] if row else None


def _current_live() -> Optional[dict]:
    row = db.execute_one(
        """
        SELECT ls.stream_name, ls.dj_id, COALESCE(d.display_name, d.username)
        FROM live_streams ls JOIN djs d ON d.id = ls.dj_id
        ORDER BY ls.started_at DESC LIMIT 1
        """
    )
    if not row:
        return None
    return {"stream_name": row[0], "dj_id": row[1], "username": row[2]}


def _rtmp_stats_for(stream_name: str) -> dict:
    """Best-effort read of live viewer count / bitrate from nginx-rtmp's stat page."""
    try:
        with urllib.request.urlopen(RTMP_STAT_URL, timeout=2) as resp:
            root = ET.fromstring(resp.read())
    except (urllib.error.URLError, ET.ParseError, TimeoutError):
        return {}

    for stream in root.iter("stream"):
        name_el = stream.find("name")
        if name_el is not None and name_el.text == stream_name:
            nclients = stream.findtext("nclients")
            bw_out = stream.findtext("bw_out")
            return {
                "viewers": int(nclients) if nclients else None,
                "bitrate": int(bw_out) if bw_out else None,
            }
    return {}


@router.get("/api/stream/status")
async def stream_status():
    live = _current_live()
    if not live:
        raise HTTPException(status_code=404, detail="No stream is live")

    stats = _rtmp_stats_for(live["stream_name"])
    return {
        "username": live["username"],
        "viewers": stats.get("viewers"),
        "bitrate": stats.get("bitrate"),
    }


# ============================================================================
# DASH manifest / segments
# ============================================================================

@router.get("/api/stream/dash/manifest.mpd")
async def dash_manifest():
    live = _current_live()
    if not live:
        raise HTTPException(status_code=404, detail="No stream is live")

    manifest_path = DASH_DIR / f"{live['stream_name']}.mpd"
    if not manifest_path.exists():
        # Publish just started - nginx-rtmp hasn't written the first fragment yet.
        raise HTTPException(status_code=404, detail="Stream is starting, try again shortly")

    return RedirectResponse(url=f"/api/stream/dash/{live['stream_name']}.mpd")
