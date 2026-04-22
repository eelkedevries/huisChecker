"""Mollie Payments API client (iDEAL, creditcard, Bancontact)."""

from __future__ import annotations

import os

import httpx

_BASE = "https://api.mollie.com/v2"


def _headers() -> dict[str, str]:
    key = os.getenv("MOLLIE_API_KEY", "")
    return {"Authorization": f"Bearer {key}"}


async def create_payment(
    *,
    session_id: str,
    address_id: str,
    buyer_email: str,
    amount_eur: str,
    redirect_url: str,
    webhook_url: str,
    description: str,
) -> dict:
    payload = {
        "amount": {"currency": "EUR", "value": amount_eur},
        "description": description,
        "redirectUrl": redirect_url,
        "webhookUrl": webhook_url,
        "metadata": {
            "session_id": session_id,
            "address_id": address_id,
            "buyer_email": buyer_email,
        },
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(_BASE + "/payments", headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()


async def get_payment(payment_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(_BASE + f"/payments/{payment_id}", headers=_headers())
        r.raise_for_status()
        return r.json()
