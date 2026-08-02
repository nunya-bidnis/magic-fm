"""
Magic.fm - Show schedule.

Timestamps are normalized to naive-UTC "YYYY-MM-DDTHH:MM:SS" for storage so
they sort correctly as plain strings, then get a "Z" appended on the way out
of every response - the frontend (player.js's formatTime, dj-dashboard's
schedule creation) always calls Date.toISOString() when sending times and
expects a normal ISO string with a timezone back.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import db
from nowplaying import require_dj

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_iso(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid datetime: {value}")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _with_z(value: str) -> str:
    return value if value.endswith("Z") else value + "Z"


class CreateShowRequest(BaseModel):
    show_name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    start_time: str
    end_time: str
    is_recurring: bool = False
    recurring_days: Optional[str] = None


@router.get("/api/schedule")
async def get_schedule():
    now = _now_str()

    current_row = db.execute_one(
        """
        SELECT show_name, description, start_time, end_time
        FROM shows WHERE start_time <= ? AND end_time > ?
        ORDER BY start_time DESC LIMIT 1
        """,
        (now, now),
    )
    current_show = None
    if current_row:
        current_show = {
            "show_name": current_row[0],
            "description": current_row[1],
            "start_time": _with_z(current_row[2]),
            "end_time": _with_z(current_row[3]),
        }

    show_rows = db.execute_query(
        """
        SELECT show_name, description, start_time, end_time, is_recurring
        FROM shows WHERE start_time > ?
        ORDER BY start_time ASC LIMIT 50
        """,
        (now,),
    )
    shows = [
        {
            "show_name": r[0], "description": r[1],
            "start_time": _with_z(r[2]), "end_time": _with_z(r[3]),
            "is_recurring": bool(r[4]),
        }
        for r in show_rows
    ]

    next_live_in_minutes = None
    if show_rows:
        next_start = datetime.fromisoformat(show_rows[0][2])
        delta = next_start - datetime.fromisoformat(now)
        next_live_in_minutes = max(0, round(delta.total_seconds() / 60))

    return {
        "current_show": current_show,
        "shows": shows,
        "next_live_in_minutes": next_live_in_minutes,
    }


@router.post("/api/schedule")
async def create_show(data: CreateShowRequest, dj: Dict = Depends(require_dj)):
    start_norm = _normalize_iso(data.start_time)
    end_norm = _normalize_iso(data.end_time)
    if end_norm <= start_norm:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    show_id = db.execute_update(
        """
        INSERT INTO shows (dj_id, show_name, description, start_time, end_time,
                            is_recurring, recurring_days)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (dj["dj_id"], data.show_name, data.description, start_norm, end_norm,
         1 if data.is_recurring else 0, data.recurring_days),
    )
    return {"status": "ok", "show_id": show_id}
