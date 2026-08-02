"""
Magic.fm - FastAPI app entry point.

Mounts every router, serves static assets, and serves the hand-written HTML
pages directly (not via StaticFiles(html=True) at the root, so that .py,
.env, .git and magic.db can never accidentally become servable files).
"""

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # must run before any module below reads os.getenv() at import time

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_tables
import admin
import auth
import autoplay
import nowplaying
import schedule
import stream

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tables()
    yield


app = FastAPI(title="Magic.fm", lifespan=lifespan)

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(nowplaying.router)
app.include_router(schedule.router)
app.include_router(autoplay.router)
app.include_router(autoplay.admin_router)
app.include_router(stream.router)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(BASE_DIR / "uploads")), name="uploads")
# Registered after stream.router so the explicit /api/stream/dash/manifest.mpd
# route (which redirects to whichever file is actually live) wins over this
# mount; every other file under the prefix (segments, the real .mpd) falls
# through to here.
app.mount("/api/stream/dash", StaticFiles(directory=str(stream.DASH_DIR)), name="dash")

HTML_PAGES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/admin.html": "admin.html",
    "/dj-login.html": "dj-login.html",
    "/dj-dashboard.html": "dj-dashboard.html",
    "/dj-nowplaying.html": "dj-nowplaying.html",
}


def _make_page_handler(filename: str):
    async def _serve():
        return FileResponse(BASE_DIR / filename)
    return _serve


for url_path, filename in HTML_PAGES.items():
    app.add_api_route(url_path, _make_page_handler(filename), methods=["GET"], include_in_schema=False)
