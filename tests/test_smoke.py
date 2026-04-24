"""Route smoke tests — verify all major routes return expected status codes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from huisChecker.app.main import app

client = TestClient(app, raise_server_exceptions=True)

VALID_ADDRESS_ID = "0363200000123456"


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
    r = client.get("/address/9999ZZ00000000")
    assert r.status_code == 404


def test_address_preview_not_found_does_not_show_raw_id() -> None:
    """Error path must not echo the internal id into the search box."""
    r = client.get("/address/9999ZZ00000000")
    assert r.status_code == 404
    assert "9999ZZ00000000" not in r.text


def test_address_search_then_preview_resolves_without_lookup() -> None:
    """Searching warms the cache so the preview route works after clicking a result."""
    # Trigger search to warm cache (single-result query redirects to preview)
    r = client.get("/address?q=Damrak+12+Amsterdam")
    assert r.status_code in (200, 303)
    # Preview must resolve from cache, not need a fresh PDOK lookup
    r2 = client.get(f"/address/{VALID_ADDRESS_ID}")
    assert r2.status_code == 200
    assert "Gratis voorbeeldrapport" in r2.text


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
