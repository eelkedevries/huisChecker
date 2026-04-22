"""SQLite-backed purchase store."""

from __future__ import annotations

from huisChecker.db import get_conn


def store_purchase(
    session_id: str,
    payment_id: str,
    address_id: str,
    buyer_email: str,
    amount_eur: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO purchases"
            " (session_id, payment_id, address_id, buyer_email, amount_eur, status)"
            " VALUES (?, ?, ?, ?, ?, 'open')",
            (session_id, payment_id, address_id, buyer_email, amount_eur),
        )


def get_purchase_by_session(session_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM purchases WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None


def get_purchase_by_payment(payment_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM purchases WHERE payment_id = ?", (payment_id,)
        ).fetchone()
        return dict(row) if row else None


def mark_paid(payment_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE purchases SET status='paid', paid_at=datetime('now') WHERE payment_id=?",
            (payment_id,),
        )
