"""Checkout, webhook, and payment-return routes."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from huisChecker.address.preview import build_preview
from huisChecker.analytics.store import track
from huisChecker.email.sender import send_report_email
from huisChecker.payment.mollie import create_payment, get_payment
from huisChecker.payment.store import (
    get_purchase_by_payment,
    get_purchase_by_session,
    mark_paid,
    store_purchase,
)
from huisChecker.payment.token import generate_token

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

REPORT_PRICE_EUR = os.getenv("REPORT_PRICE_EUR", "9.95")

router = APIRouter()


def _base_url(request: Request) -> str:
    configured = os.getenv("APP_BASE_URL", "").rstrip("/")
    return configured or str(request.base_url).rstrip("/")


@router.get("/checkout/{address_id}", response_class=HTMLResponse, response_model=None)
async def checkout_get(request: Request, address_id: str) -> Response:
    preview = build_preview(address_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Adres niet gevonden")
    track("checkout_started", address_id)
    return templates.TemplateResponse(
        request,
        "checkout.html",
        {"preview": preview, "price": REPORT_PRICE_EUR},
    )


@router.post("/checkout/{address_id}", response_model=None)
async def checkout_post(
    request: Request,
    address_id: str,
    email: str = Form(...),
) -> Response:
    preview = build_preview(address_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Adres niet gevonden")

    session_id = str(uuid.uuid4())
    base = _base_url(request)
    redirect_url = f"{base}/payment/return?session_id={session_id}"
    webhook_url = f"{base}/payment/webhook"

    mollie_key = os.getenv("MOLLIE_API_KEY", "")
    if not mollie_key:
        # Dev mode without Mollie: simulate paid purchase and go straight to report.
        token = generate_token(address_id)
        store_purchase(
            session_id=session_id,
            payment_id=f"dev_{session_id}",
            address_id=address_id,
            buyer_email=email,
            amount_eur=REPORT_PRICE_EUR,
        )
        mark_paid(f"dev_{session_id}")
        track("purchase_completed", address_id)
        logger.info("[DEV] No MOLLIE_API_KEY; simulating purchase for %s", address_id)
        return RedirectResponse(
            url=f"/report?id={address_id}&token={token}", status_code=303
        )

    try:
        payment = await create_payment(
            session_id=session_id,
            address_id=address_id,
            buyer_email=email,
            amount_eur=REPORT_PRICE_EUR,
            redirect_url=redirect_url,
            webhook_url=webhook_url,
            description=f"huisChecker rapport: {preview.display_address}",
        )
    except Exception:
        logger.exception("Mollie create_payment failed")
        raise HTTPException(status_code=502, detail="Betaalsysteem tijdelijk niet beschikbaar")

    store_purchase(
        session_id=session_id,
        payment_id=payment["id"],
        address_id=address_id,
        buyer_email=email,
        amount_eur=REPORT_PRICE_EUR,
    )
    checkout_url = payment["_links"]["checkout"]["href"]
    return RedirectResponse(url=checkout_url, status_code=303)


@router.post("/payment/webhook", response_model=None)
async def payment_webhook(request: Request) -> Response:
    """Mollie posts form-encoded `id=<payment_id>` here after status change."""
    form = await request.form()
    payment_id = str(form.get("id", "")).strip()
    if not payment_id:
        return Response(status_code=200)

    try:
        payment = await get_payment(payment_id)
    except Exception:
        logger.exception("Mollie get_payment failed for %s", payment_id)
        return Response(status_code=200)

    if payment.get("status") != "paid":
        return Response(status_code=200)

    # Idempotency: skip if already marked paid.
    existing = get_purchase_by_payment(payment_id)
    if existing and existing["status"] == "paid":
        return Response(status_code=200)

    mark_paid(payment_id)
    metadata = payment.get("metadata") or {}
    address_id = metadata.get("address_id", "")
    buyer_email = metadata.get("buyer_email", "")
    track("purchase_completed", address_id)

    if buyer_email and address_id:
        preview = build_preview(address_id)
        display = preview.display_address if preview else address_id
        token = generate_token(address_id)
        base = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
        report_url = f"{base}/report?id={address_id}&token={token}"
        await send_report_email(
            to_email=buyer_email,
            address_display=display,
            report_url=report_url,
        )

    return Response(status_code=200)


@router.get("/payment/return", response_class=HTMLResponse, response_model=None)
async def payment_return(request: Request, session_id: str = "") -> Response:
    if not session_id:
        raise HTTPException(status_code=400, detail="Ontbrekende sessie-id")

    purchase = get_purchase_by_session(session_id)
    if purchase is None:
        raise HTTPException(status_code=404, detail="Sessie niet gevonden")

    if purchase["status"] == "paid":
        token = generate_token(purchase["address_id"])
        return RedirectResponse(
            url=f"/report?id={purchase['address_id']}&token={token}", status_code=303
        )

    return templates.TemplateResponse(
        request,
        "payment_return.html",
        {"status": purchase["status"], "session_id": session_id},
    )


@router.get("/payment/status", response_model=None)
async def payment_status(session_id: str = "") -> JSONResponse:
    if not session_id:
        return JSONResponse({"status": "unknown"}, status_code=400)
    purchase = get_purchase_by_session(session_id)
    if purchase is None:
        return JSONResponse({"status": "unknown"}, status_code=404)
    result: dict = {"status": purchase["status"]}
    if purchase["status"] == "paid":
        token = generate_token(purchase["address_id"])
        result["report_url"] = f"/report?id={purchase['address_id']}&token={token}"
    return JSONResponse(result)
