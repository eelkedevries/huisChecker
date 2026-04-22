"""Route smoke tests — verify all major routes return expected status codes."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from huisChecker.app.main import app

client = TestClient(app, raise_server_exceptions=True)

VALID_ADDRESS_ID = "1011AB-12"


def test_import() -> None:
    import huisChecker  # noqa: F401


def test_home_returns_200() -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "huisChecker" in r.text


def test_methodology_returns_200() -> None:
    r = client.get("/methodology")
    assert r.status_code == 200
    assert "Methode" in r.text
    assert "Geen samengestelde score" in r.text


def test_methodology_has_no_placeholder() -> None:
    r = client.get("/methodology")
    assert "volgt zodra" not in r.text


def test_explore_returns_200() -> None:
    r = client.get("/explore")
    assert r.status_code == 200


def test_address_no_query_returns_200() -> None:
    r = client.get("/address")
    assert r.status_code == 200


def test_address_search_no_match_returns_200() -> None:
    r = client.get("/address?q=zzznietbestaandadres999")
    assert r.status_code == 200


def test_address_preview_valid_returns_200() -> None:
    r = client.get(f"/address/{VALID_ADDRESS_ID}")
    assert r.status_code == 200
    assert "Gratis voorbeeldrapport" in r.text


def test_address_preview_invalid_returns_404() -> None:
    r = client.get("/address/ONBEKEND-00")
    assert r.status_code == 404


def test_report_no_id_returns_400_with_error_page() -> None:
    r = client.get("/report")
    assert r.status_code == 400
    assert "Rapport niet gevonden" in r.text


def test_report_valid_id_returns_200_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("REPORT_FREE_ACCESS", "1")
    r = client.get(f"/report?id={VALID_ADDRESS_ID}")
    assert r.status_code == 200
    assert "Woningrapport" in r.text


def test_report_has_sections_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("REPORT_FREE_ACCESS", "1")
    r = client.get(f"/report?id={VALID_ADDRESS_ID}")
    body = r.text
    assert "Woning en gebouw" in body
    assert "Buurtprofiel" in body
    assert "Leefbaarheid" in body
    assert "Veiligheid en overlast" in body
    assert "Klimaat en leefomgeving" in body
    assert "Bronnen en kanttekeningen" in body


def test_report_has_no_english_caveats_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("REPORT_FREE_ACCESS", "1")
    r = client.get(f"/report?id={VALID_ADDRESS_ID}")
    body = r.text
    assert "real-world state may differ" not in body
    assert "PC4 averages" not in body
    assert "shown as-is" not in body
    assert "under-reporting varies" not in body


def test_report_pdf_no_id_returns_400() -> None:
    r = client.get("/report.pdf")
    assert r.status_code == 400


def test_report_pdf_no_access_returns_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REPORT_FREE_ACCESS", "0")
    r = client.get(f"/report.pdf?id={VALID_ADDRESS_ID}&token=invalid")
    assert r.status_code == 403


def test_checkout_valid_address_returns_200() -> None:
    r = client.get(f"/checkout/{VALID_ADDRESS_ID}")
    assert r.status_code == 200
    assert "Volledig rapport" in r.text


def test_unknown_route_returns_404() -> None:
    r = client.get("/dit-bestaat-niet-xyz")
    assert r.status_code == 404


def test_methodology_sources_all_present() -> None:
    r = client.get("/methodology")
    body = r.text
    assert "BAG" in body
    assert "CBS" in body
    assert "Leefbaarometer" in body
    assert "Politie" in body
    assert "Klimaateffectatlas" in body


def test_report_sources_section_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("REPORT_FREE_ACCESS", "1")
    r = client.get(f"/report?id={VALID_ADDRESS_ID}")
    body = r.text
    assert "Bronnen en kanttekeningen" in body
    assert "Geen samengestelde" in body
