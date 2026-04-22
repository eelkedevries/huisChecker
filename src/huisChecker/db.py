"""Shared SQLite database: connection helper and schema init."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def _db_path() -> Path:
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    data_dir.mkdir(exist_ok=True)
    return data_dir / "huisChecker.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS purchases (
                session_id  TEXT PRIMARY KEY,
                payment_id  TEXT UNIQUE,
                address_id  TEXT NOT NULL,
                buyer_email TEXT NOT NULL,
                amount_eur  TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'open',
                created_at  TEXT DEFAULT (datetime('now')),
                paid_at     TEXT
            );
            CREATE TABLE IF NOT EXISTS analytics_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                event      TEXT NOT NULL,
                address_id TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
