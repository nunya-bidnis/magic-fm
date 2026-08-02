"""
Magic.fm - Site <-> Discord chat bridge (outbound half).

Visitors chat under a nickname only - no account, no password, nothing
persisted beyond the message itself. Every message is stored locally (so
GET /api/chat/messages has something to serve even if Discord is briefly
unreachable) and relayed out via a Discord webhook.

The inbound half (real Discord users' messages appearing back on the site)
is handled by a separate always-running process - discord_bot.py - because
reading Discord requires a persistent Gateway websocket connection, which
doesn't fit a request-driven ASGI app. That process writes directly into the
same chat_messages table this module reads from.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import db

logger = logging.getLogger(__name__)

router = APIRouter()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


class PostMessageRequest(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=32)
    message: str = Field(..., min_length=1, max_length=2000)


def _relay_to_discord(nickname: str, message: str) -> None:
    """Best-effort: a visitor's message is stored locally regardless of whether
    Discord is reachable, so this never blocks or fails the site-side post."""
    if not DISCORD_WEBHOOK_URL:
        return
    body = json.dumps({"content": message, "username": nickname}).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=3)
    except (urllib.error.URLError, TimeoutError) as e:
        logger.warning("Discord webhook relay failed: %s", e)


@router.post("/api/chat/messages")
async def post_message(data: PostMessageRequest):
    nickname = data.nickname.strip()
    message = data.message.strip()
    if not nickname or not message:
        raise HTTPException(status_code=400, detail="Nickname and message are required")

    db.execute_update(
        "INSERT INTO chat_messages (source, nickname, message) VALUES ('site', ?, ?)",
        (nickname, message),
    )
    _relay_to_discord(nickname, message)

    return {"status": "ok"}


@router.get("/api/chat/messages")
async def get_messages(limit: int = 50) -> List[Dict]:
    limit = max(1, min(limit, 200))
    rows = db.execute_query(
        """
        SELECT nickname, message, created_at FROM chat_messages
        ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    )
    # Reversed so the response reads oldest-to-newest, top-to-bottom like a
    # normal chat log - chat.js displays the array in the order it arrives.
    return [
        {
            "discord_username": r[0],
            "message": r[1],
            "timestamp": r[2] + ("Z" if not r[2].endswith("Z") else ""),
        }
        for r in reversed(rows)
    ]
