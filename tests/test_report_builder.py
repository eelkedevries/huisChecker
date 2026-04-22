"""Tests for the full paid-report builder and routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from huisChecker.app.main import app
from huisChecker.report import (
    FullReport,
    ReportModuleKey,
    build_full_report,
    report_module_registry,
)

ADDRESS_ID = "0363200000123456"


def test_build_full_report_returns_none_for_unknown_address() -> None:
    assert build_full_report("NOPE-0") is None


def test_build_full_report_structure() -> None:
    report = build_full_report(ADDRESS_ID)
    assert isinstance(report, FullReport)
    assert report.address_id == ADDRESS_ID
    assert report.display_address.startswith("Damrak 12")
    assert report.postcode4 == "1011"

    section_keys = [s.key for s in report.sections]
    expected = [k.value for k in ReportModuleKey]
    assert section_keys == expected, "every module key must appear in registry order"


def test_executive_summary_has_no_composite_score() -> None:
    report = build_full_report(ADDRESS_ID)
    assert report is not None
    joined = " ".join(report.executive_summary).lower()
    for forbidden in ("totaal", "overall", "samengestelde score", "huischecker-score"):
        if forbidden == "samengestelde score":
            # we explicitly disclaim this; check the disclaimer wording is present once
            assert "samengestelde score" in joined
        else:
            assert forbidden not in joined


def test_section_caveats_match_module_contracts() -> None:
    report = build_full_report(ADDRESS_ID)
    assert report is not None
    for section in report.sections:
        contract = report_module_registry.get(section.key)
        assert section.caveat == contract.caveat
        assert section.label == contract.label


def test_area_section_includes_benchmark_against_national() -> None:
    report = build_full_report(ADDRESS_ID)
    assert report is not None
    area = next(s for s in report.sections if s.key == ReportModuleKey.AREA_PROFILE.value)
    assert area.findings, "area section must surface at least one finding"
    finding = area.findings[0]
    assert finding.comparison_label in (
        "boven gemiddelde",
        "rond gemiddelde",
        "onder gemiddelde",
    )
    assert "Nederland" in (finding.comparison_detail or "")


def test_safety_section_uses_inverted_benchmark() -> None:
    report = build_full_report(ADDRESS_ID)
    assert report is not None
    safety = next(s for s in report.sections if s.key == ReportModuleKey.SAFETY_NUISANCE.value)
    assert safety.findings
    finding = safety.findings[0]
    assert finding.comparison_label in (
        "beter dan gemiddeld",
        "rond gemiddelde",
        "slechter dan gemiddeld",
    )


def test_sources_listing_covers_used_datasets() -> None:
    report = build_full_report(ADDRESS_ID)
    assert report is not None
    keys = {s.key for s in report.sources}
    for required in ("bag", "cbs_kerncijfers_pc4", "leefbaarometer", "politie_opendata"):
        assert required in keys, f"missing source listing: {required}"


def test_report_route_renders_full_report() -> None:
    client = TestClient(app)
    resp = client.get(f"/report?id={ADDRESS_ID}")
    assert resp.status_code == 200
    body = resp.text
    assert "Volledig rapport" in body or "Volledig" in body
    assert "Damrak 12" in body
    assert "Bronnen en kanttekeningen" in body
    assert "Leefbaarometer" in body
    # No opaque composite score should be presented as a metric.
    for forbidden in ("Eindscore", "Totaalscore", "Overall score"):
        assert forbidden not in body


def test_report_route_404s_for_unknown_address() -> None:
    client = TestClient(app)
    resp = client.get("/report?id=NOPE-0")
    assert resp.status_code == 404


def test_report_pdf_route_returns_pdf_or_503() -> None:
    client = TestClient(app)
    resp = client.get(f"/report.pdf?id={ADDRESS_ID}")
    # WeasyPrint may not have its system libraries available in CI;
    # accept either a real PDF response or the documented 503 fallback.
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"
