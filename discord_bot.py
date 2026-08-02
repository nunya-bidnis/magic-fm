"""
Magic.fm - Discord -> site chat relay (inbound half).

Runs as its own always-on process (magic-fm-discord-bot.service), separate
from the FastAPI app, because reading Discord requires a persistent Gateway
websocket connection that doesn't fit a request-driven ASGI process. It
writes straight into the same chat_messages table chat.py serves from - no
HTTP call back into the app needed, they just share the SQLite file.

Restricted to a single channel two ways on purpose (belt-and-suspenders,
same pattern as the admin loopback gate): the bot should only be invited
with permission on that one channel in Discord's own settings, and this
code independently ignores anything from a different channel ID in case
that permission is ever misconfigured.

Skips any message with a webhook_id (i.e. anything posted via our own
outbound webhook in chat.py) and anything from another bot, so a visitor's
site message doesn't loop back in as a second "Discord" message.
"""

import logging
import os
import sys

import discord
from dotenv import load_dotenv

load_dotenv()

from database import db, init_tables

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("discord_bot")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID", "")

if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
    logger.error("DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID must be set in .env - exiting")
    sys.exit(1)

CHANNEL_ID = int(DISCORD_CHANNEL_ID)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    logger.info("Connected to Discord as %s, watching channel %s", client.user, CHANNEL_ID)


@client.event
async def on_message(message: discord.Message):
    if message.channel.id != CHANNEL_ID:
        return
    if message.webhook_id is not None or message.author.bot:
        return
    if not message.content.strip():
        return

    db.execute_update(
        "INSERT INTO chat_messages (source, nickname, message, discord_message_id) "
        "VALUES ('discord', ?, ?, ?)",
        (message.author.display_name, message.content, str(message.id)),
    )


if __name__ == "__main__":
    init_tables()
    client.run(DISCORD_BOT_TOKEN)
