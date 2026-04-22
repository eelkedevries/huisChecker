"""Transactional email via Resend API."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


def _html_body(address_display: str, report_url: str) -> str:  # noqa: E501
    btn = (
        f'<a href="{report_url}" style="background:#1e293b;color:#fff;'
        'padding:12px 24px;text-decoration:none;border-radius:8px;'
        'display:inline-block;font-weight:600;">Bekijk uw rapport &rarr;</a>'
    )
    return (
        "<p>Geachte koper,</p>"
        f"<p>Bedankt voor uw aankoop. Uw huisChecker rapport voor"
        f" <strong>{address_display}</strong> is beschikbaar.</p>"
        f"<p>{btn}</p>"
        '<p style="color:#94a3b8;font-size:12px;">'
        "Deze link is 1 jaar geldig. U hoeft geen account aan te maken.</p>"
        '<hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;" />'
        '<p style="color:#94a3b8;font-size:12px;">'
        "huisChecker &middot; Woningrapport op basis van openbare data</p>"
    )


async def send_report_email(
    *, to_email: str, address_display: str, report_url: str
) -> bool:
    api_key = os.getenv("RESEND_API_KEY", "")
    from_addr = os.getenv("FROM_EMAIL", "huisChecker <noreply@huischecker.nl>")

    if not api_key:
        logger.info(
            "[DEV] Email skipped (no RESEND_API_KEY). Would send to %s: %s",
            to_email,
            report_url,
        )
        return True

    payload = {
        "from": from_addr,
        "to": [to_email],
        "subject": f"Uw huisChecker rapport: {address_display}",
        "html": _html_body(address_display, report_url),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            if not r.is_success:
                logger.error("Resend error %s: %s", r.status_code, r.text)
            return r.is_success
    except Exception:
        logger.exception("send_report_email failed")
        return False
