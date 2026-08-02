"""
Magic.fm - Database layer

Thin wrapper around sqlite3 exposing a module-level `db` singleton plus
init_tables() to create the schema. SQLite is single-writer, so every
connection uses check_same_thread=False with a lock around writes to keep
concurrent FastAPI requests from tripping over each other.
"""

import os
import sqlite3
import threading
from typing import Any, List, Optional, Tuple

DATABASE_PATH = os.getenv("DATABASE_PATH", "./magic.db")


class Database:
    def __init__(self, path: str):
        self.path = path
        self._local = threading.local()
        self._write_lock = threading.Lock()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return conn

    def execute_query(self, sql: str, params: Tuple = ()) -> List[Tuple]:
        cur = self._conn().execute(sql, params)
        return cur.fetchall()

    def execute_one(self, sql: str, params: Tuple = ()) -> Optional[Tuple]:
        cur = self._conn().execute(sql, params)
        return cur.fetchone()

    def execute_update(self, sql: str, params: Tuple = ()) -> int:
        """Run an INSERT/UPDATE/DELETE. Returns lastrowid (for INSERT) or rowcount."""
        with self._write_lock:
            conn = self._conn()
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid if cur.lastrowid else cur.rowcount


db = Database(DATABASE_PATH)


def init_tables() -> None:
    conn = db._conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS djs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            notes TEXT,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_login TEXT,
            FOREIGN KEY (created_by) REFERENCES djs(id)
        );

        CREATE TABLE IF NOT EXISTS stream_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dj_id INTEGER NOT NULL,
            stream_key TEXT UNIQUE NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_used TEXT,
            FOREIGN KEY (dj_id) REFERENCES djs(id)
        );

        CREATE TABLE IF NOT EXISTS metadata_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dj_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (dj_id) REFERENCES djs(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dj_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (dj_id) REFERENCES djs(id)
        );

        CREATE TABLE IF NOT EXISTS nowplaying (
            dj_id INTEGER PRIMARY KEY,
            track TEXT NOT NULL,
            artist TEXT,
            art_url TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (dj_id) REFERENCES djs(id)
        );

        CREATE TABLE IF NOT EXISTS shows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dj_id INTEGER NOT NULL,
            show_name TEXT NOT NULL,
            description TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            is_recurring INTEGER NOT NULL DEFAULT 0,
            recurring_days TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (dj_id) REFERENCES djs(id)
        );

        CREATE TABLE IF NOT EXISTS autoplay_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT,
            source TEXT NOT NULL,
            source_url TEXT,
            license_note TEXT,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            play_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS live_streams (
            stream_name TEXT PRIMARY KEY,
            dj_id INTEGER NOT NULL,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (dj_id) REFERENCES djs(id)
        );

        CREATE TABLE IF NOT EXISTS autoplay_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            artist TEXT,
            requested_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (library_id) REFERENCES autoplay_library(id)
        );

        CREATE INDEX IF NOT EXISTS idx_stream_keys_dj ON stream_keys(dj_id);
        CREATE INDEX IF NOT EXISTS idx_metadata_tokens_dj ON metadata_tokens(dj_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_shows_start ON shows(start_time);
        CREATE INDEX IF NOT EXISTS idx_autoplay_queue_created ON autoplay_queue(created_at);
        """
    )
    conn.commit()


# create_dummy_dj.py (and any other bootstrap script) imports init_db - keep
# both names pointing at the same schema setup so neither contract breaks.
init_db = init_tables
