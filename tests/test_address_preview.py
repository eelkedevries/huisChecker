"""Tests for free preview assembly on PDOK-resolved addresses."""

from __future__ import annotations

from pathlib import Path

import pytest

from huisChecker.address.preview import AddressPreview, build_preview
from huisChecker.etl.base import JobContext, SourceMode
from huisChecker.etl.pipeline import run_smoke

AMSTERDAM_DAMRAK = "0363200000123456"
AMSTERDAM_NIEUWENDIJK = "0363200000123457"
ROTTERDAM_COOLSINGEL = "0599200000123458"
UTRECHT_OUDEGRACHT = "0344200000123459"
LEIDEN_BREESTRAAT = "0546200000999999"


@pytest.fixture()
def data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    fixtures = Path(__file__).resolve().parents[1] / "src/huisChecker/etl/fixtures"
    ctx = JobContext(
        data_root=root,
        curated_root=root / "curated",
        manifests_root=root / "manifests",
        fixtures_root=fixtures,
        mode=SourceMode.FIXTURE,
    )
    run_smoke(ctx)
    return root


def test_preview_returns_none_for_unknown_id(data_root: Path) -> None:
    assert build_preview("UNKNOWN-0", data_root=data_root) is None


def test_preview_amsterdam_address(data_root: Path) -> None:
    p = build_preview(AMSTERDAM_DAMRAK, data_root=data_root)
    assert p is not None
    assert isinstance(p, AddressPreview)
    assert p.address_id == AMSTERDAM_DAMRAK
    assert "Damrak" in p.display_address
    assert "Amsterdam" in p.display_address
    assert p.postcode4 == "1011"
    assert p.municipality_name == "Amsterdam"
    assert p.province_name == "Noord-Holland"
    assert p.is_partial is False


def test_preview_building_fields(data_root: Path) -> None:
    p = build_preview(AMSTERDAM_DAMRAK, data_root=data_root)
    assert p is not None
    assert p.construction_year == "1925"
    assert p.surface_area_m2 == "78"
    assert p.use_purpose == "wonen"


def test_preview_with_mixed_use_purpose(data_root: Path) -> None:
    p = build_preview(AMSTERDAM_NIEUWENDIJK, data_root=data_root)
    assert p is not None
    assert p.use_purpose is not None
    assert "wonen" in p.use_purpose
    assert "winkel" in p.use_purpose


def test_preview_area_metrics(data_root: Path) -> None:
    p = build_preview(AMSTERDAM_DAMRAK, data_root=data_root)
    assert p is not None
    assert p.leefbaarometer_score == "5.8"
    assert p.leefbaarometer_band == "voldoende"
    assert p.flood_probability_class == "middelgroot"
    assert p.heat_stress_class == "groot"
    assert p.road_noise_class == "zeer_hoog"
    assert p.incidents_per_1000 is not None
    assert p.population_density is not None


def test_preview_signals_caution_for_heat_noise(data_root: Path) -> None:
    p = build_preview(AMSTERDAM_DAMRAK, data_root=data_root)
    assert p is not None
    caution_text = " ".join(p.cautions)
    assert "hittestress" in caution_text.lower()
    assert "geluidbelasting" in caution_text.lower()


def test_preview_strength_for_utrecht(data_root: Path) -> None:
    p = build_preview(UTRECHT_OUDEGRACHT, data_root=data_root)
    assert p is not None
    assert p.leefbaarometer_band == "goed"
    assert p.flood_probability_class == "klein"
    strength_text = " ".join(p.strengths)
    assert "leefbaarheid" in strength_text.lower()
    assert "overstromingsrisico" in strength_text.lower()


def test_preview_caution_for_rotterdam_flood(data_root: Path) -> None:
    p = build_preview(ROTTERDAM_COOLSINGEL, data_root=data_root)
    assert p is not None
    assert p.flood_probability_class == "groot"
    caution_text = " ".join(p.cautions)
    assert "overstromingsrisico" in caution_text.lower()


def test_preview_reference_periods_set(data_root: Path) -> None:
    p = build_preview(AMSTERDAM_DAMRAK, data_root=data_root)
    assert p is not None
    assert p.bag_reference_period
    assert p.cbs_reference_period
    assert p.leefbaarometer_reference_period
    assert p.politie_reference_period
    assert p.klimaat_reference_period


def test_preview_display_address_format(data_root: Path) -> None:
    p = build_preview(AMSTERDAM_NIEUWENDIJK, data_root=data_root)
    assert p is not None
    assert "Nieuwendijk" in p.display_address
    assert "5" in p.display_address
    assert "A" in p.display_address
    assert "Amsterdam" in p.display_address


def test_preview_partial_for_address_outside_curated(data_root: Path) -> None:
    p = build_preview(LEIDEN_BREESTRAAT, data_root=data_root)
    assert p is not None
    assert p.is_partial is True
    assert p.municipality_name == "Leiden"
    assert p.province_name == "Zuid-Holland"
    assert p.latitude is not None and p.longitude is not None
    # No curated BAG or PC4 metrics for this address.
    assert p.construction_year is None
    assert p.leefbaarometer_score is None
    assert p.missing_layers  # lists the gaps


def test_preview_missing_curated_still_resolves_partial(tmp_path: Path) -> None:
    """No curated data at all: preview still renders from PDOK as partial."""
    empty = tmp_path / "empty"
    empty.mkdir()
    p = build_preview(AMSTERDAM_DAMRAK, data_root=empty)
    assert p is not None
    assert p.is_partial is True
    assert p.construction_year is None
