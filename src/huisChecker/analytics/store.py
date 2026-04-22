"""Analytics event tracking (SQLite)."""

from __future__ import annotations

import logging

from huisChecker.db import get_conn

logger = logging.getLogger(__name__)


def track(event: str, address_id: str | None = None) -> None:
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO analytics_events (event, address_id) VALUES (?, ?)",
                (event, address_id),
            )
    except Exception:
        logger.exception("analytics track failed: %s", event)
