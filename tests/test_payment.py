"""Tests for payment entitlement, token signing, purchase store, and routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Token tests
# ---------------------------------------------------------------------------


def test_token_roundtrip(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    from huisChecker.payment.token import generate_token, validate_token

    token = generate_token("0363200012073415")
    assert validate_token(token) == "0363200012073415"


def test_token_wrong_address(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    from huisChecker.payment.token import generate_token, validate_token

    token = generate_token("addr-A")
    assert validate_token(token) != "addr-B"


def test_token_expired(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    from huisChecker.payment.token import generate_token, validate_token

    token = generate_token("addr-X")
    assert validate_token(token, max_age=-1) is None


def test_token_tampered(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    from huisChecker.payment.token import generate_token, validate_token

    token = generate_token("addr-Y")
    tampered = token[:-4] + "XXXX"
    assert validate_token(tampered) is None


# ---------------------------------------------------------------------------
# Purchase store tests
# The store reads DATA_DIR env var on each call, so monkeypatching works.
# ---------------------------------------------------------------------------


def _init(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from huisChecker.db import init_db
    init_db()


def test_store_purchase_and_get(tmp_path, monkeypatch):
    _init(tmp_path, monkeypatch)
    from huisChecker.payment.store import get_purchase_by_session, store_purchase

    store_purchase("s1", "tr_001", "addr-1", "a@b.com", "9.95")
    row = get_purchase_by_session("s1")
    assert row is not None
    assert row["address_id"] == "addr-1"
    assert row["status"] == "open"


def test_mark_paid(tmp_path, monkeypatch):
    _init(tmp_path, monkeypatch)
    from huisChecker.payment.store import (
        get_purchase_by_session,
        mark_paid,
        store_purchase,
    )

    store_purchase("s2", "tr_002", "addr-2", "b@c.com", "9.95")
    mark_paid("tr_002")
    assert get_purchase_by_session("s2")["status"] == "paid"


def test_get_by_payment(tmp_path, monkeypatch):
    _init(tmp_path, monkeypatch)
    from huisChecker.payment.store import get_purchase_by_payment, store_purchase

    store_purchase("s3", "tr_003", "addr-3", "c@d.com", "9.95")
    row = get_purchase_by_payment("tr_003")
    assert row is not None
    assert row["session_id"] == "s3"


def test_get_unknown_session_returns_none(tmp_path, monkeypatch):
    _init(tmp_path, monkeypatch)
    from huisChecker.payment.store import get_purchase_by_session

    assert get_purchase_by_session("does-not-exist") is None


def test_mark_paid_idempotent(tmp_path, monkeypatch):
    _init(tmp_path, monkeypatch)
    from huisChecker.payment.store import (
        get_purchase_by_session,
        mark_paid,
        store_purchase,
    )

    store_purchase("s4", "tr_004", "addr-4", "d@e.com", "9.95")
    mark_paid("tr_004")
    mark_paid("tr_004")  # second call must not raise
    assert get_purchase_by_session("s4")["status"] == "paid"


# ---------------------------------------------------------------------------
# Report route entitlement (production mode, no free access)
# ---------------------------------------------------------------------------


@pytest.fixture()
def prod_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REPORT_FREE_ACCESS", "0")
    monkeypatch.setenv("SECRET_KEY", "route-test-secret")

    from huisChecker.db import init_db
    init_db()

    from huisChecker.app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_report_no_token_redirects_to_checkout(prod_client):
    r = prod_client.get("/report?id=0363200012073415", follow_redirects=False)
    assert r.status_code == 303
    assert "/checkout/" in r.headers["location"]


def test_report_invalid_token_redirects(prod_client):
    r = prod_client.get(
        "/report?id=0363200012073415&token=garbage", follow_redirects=False
    )
    assert r.status_code == 303
    assert "/checkout/" in r.headers["location"]


def test_report_valid_token_passes_gate(prod_client, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "route-test-secret")
    from huisChecker.payment.token import generate_token

    token = generate_token("0363200012073415")
    r = prod_client.get(
        f"/report?id=0363200012073415&token={token}", follow_redirects=False
    )
    # Token is valid → gate opens. May be 200 or 404 depending on data, but NOT 303.
    assert r.status_code != 303


def test_pdf_no_token_returns_403(prod_client):
    r = prod_client.get("/report.pdf?id=0363200012073415")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


@pytest.fixture()
def webhook_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MOLLIE_API_KEY", "test_dummy")
    monkeypatch.setenv("SECRET_KEY", "webhook-secret")
    monkeypatch.setenv("RESEND_API_KEY", "")

    from huisChecker.db import init_db
    init_db()

    from huisChecker.app.main import app
    return TestClient(app)


def test_webhook_empty_body_returns_200(webhook_client):
    r = webhook_client.post("/payment/webhook", data={})
    assert r.status_code == 200


def test_webhook_mollie_error_returns_200(webhook_client, monkeypatch):
    import huisChecker.app.routes.checkout as checkout_mod

    async def _bad_get(payment_id):
        raise RuntimeError("network error")

    monkeypatch.setattr(checkout_mod, "get_payment", _bad_get)
    r = webhook_client.post("/payment/webhook", data={"id": "tr_fail"})
    assert r.status_code == 200


def test_webhook_paid_marks_db(webhook_client, monkeypatch, tmp_path):
    import huisChecker.app.routes.checkout as checkout_mod
    from huisChecker.payment import store as store_mod

    store_mod.store_purchase("wh-s", "tr_p1", "addr-wh", "wh@x.com", "9.95")

    async def _fake_get(payment_id):
        return {
            "id": payment_id,
            "status": "paid",
            "metadata": {
                "session_id": "wh-s",
                "address_id": "addr-wh",
                "buyer_email": "wh@x.com",
            },
        }

    monkeypatch.setattr(checkout_mod, "get_payment", _fake_get)
    r = webhook_client.post("/payment/webhook", data={"id": "tr_p1"})
    assert r.status_code == 200
    assert store_mod.get_purchase_by_payment("tr_p1")["status"] == "paid"


# ---------------------------------------------------------------------------
# Payment status endpoint
# ---------------------------------------------------------------------------


def test_payment_status_unknown(webhook_client):
    r = webhook_client.get("/payment/status?session_id=nonexistent")
    assert r.status_code == 404


def test_payment_status_paid_has_report_url(webhook_client, tmp_path, monkeypatch):
    from huisChecker.payment import store as store_mod

    store_mod.store_purchase("s-pd", "tr_pd", "addr-z", "z@z.com", "9.95")
    store_mod.mark_paid("tr_pd")

    r = webhook_client.get("/payment/status?session_id=s-pd")
    data = r.json()
    assert data["status"] == "paid"
    assert "report_url" in data
    assert "addr-z" in data["report_url"]


# ---------------------------------------------------------------------------
# Dev mode: checkout with no MOLLIE_API_KEY simulates purchase
# ---------------------------------------------------------------------------


def test_dev_checkout_no_mollie_key(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MOLLIE_API_KEY", "")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "dev-checkout-secret")

    from huisChecker.db import init_db
    init_db()
    from huisChecker.app.main import app

    client = TestClient(app)
    r = client.post(
        "/checkout/0363200000123456",
        data={"email": "dev@test.com"},
        follow_redirects=False,
    )
    # Should redirect to /report?id=...&token=...
    assert r.status_code == 303
    assert "/report" in r.headers["location"]
    assert "token=" in r.headers["location"]
