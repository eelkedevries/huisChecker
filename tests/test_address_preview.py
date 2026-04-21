"""Tests for free preview assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from huisChecker.address.preview import AddressPreview, build_preview
from huisChecker.etl.base import JobContext, SourceMode
from huisChecker.etl.pipeline import run_smoke


@pytest.fixture(scope="module")
def data_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("data")
    root = tmp / "data"
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
    p = build_preview("1011AB-12", data_root=data_root)
    assert p is not None
    assert isinstance(p, AddressPreview)
    assert p.address_id == "1011AB-12"
    assert "Damrak" in p.display_address
    assert "Amsterdam" in p.display_address
    assert p.postcode4 == "1011"
    assert p.municipality_name == "Amsterdam"
    assert p.province_name == "Noord-Holland"


def test_preview_building_fields(data_root: Path) -> None:
    p = build_preview("1011AB-12", data_root=data_root)
    assert p is not None
    assert p.construction_year == "1925"
    assert p.surface_area_m2 == "78"
    assert p.use_purpose == "wonen"


def test_preview_with_mixed_use_purpose(data_root: Path) -> None:
    p = build_preview("1012AB-5-A", data_root=data_root)
    assert p is not None
    assert p.use_purpose is not None
    assert "wonen" in p.use_purpose
    assert "winkel" in p.use_purpose


def test_preview_area_metrics(data_root: Path) -> None:
    p = build_preview("1011AB-12", data_root=data_root)
    assert p is not None
    assert p.leefbaarometer_score == "5.8"
    assert p.leefbaarometer_band == "voldoende"
    assert p.flood_probability_class == "middelgroot"
    assert p.heat_stress_class == "groot"
    assert p.road_noise_class == "zeer_hoog"
    assert p.incidents_per_1000 is not None
    assert p.population_density is not None


def test_preview_signals_caution_for_heat_noise(data_root: Path) -> None:
    p = build_preview("1011AB-12", data_root=data_root)
    assert p is not None
    caution_text = " ".join(p.cautions)
    assert "hittestress" in caution_text.lower()
    assert "geluidbelasting" in caution_text.lower()


def test_preview_strength_for_utrecht(data_root: Path) -> None:
    p = build_preview("3511AB-7", data_root=data_root)
    assert p is not None
    assert p.leefbaarometer_band == "goed"
    assert p.flood_probability_class == "klein"
    strength_text = " ".join(p.strengths)
    assert "leefbaarheid" in strength_text.lower()
    assert "overstromingsrisico" in strength_text.lower()


def test_preview_caution_for_rotterdam_flood(data_root: Path) -> None:
    p = build_preview("3011AB-42", data_root=data_root)
    assert p is not None
    assert p.flood_probability_class == "groot"
    caution_text = " ".join(p.cautions)
    assert "overstromingsrisico" in caution_text.lower()


def test_preview_reference_periods_set(data_root: Path) -> None:
    p = build_preview("1011AB-12", data_root=data_root)
    assert p is not None
    assert p.bag_reference_period
    assert p.cbs_reference_period
    assert p.leefbaarometer_reference_period
    assert p.politie_reference_period
    assert p.klimaat_reference_period


def test_preview_display_address_format(data_root: Path) -> None:
    p = build_preview("1012AB-5-A", data_root=data_root)
    assert p is not None
    assert "Nieuwendijk" in p.display_address
    assert "5" in p.display_address
    assert "A" in p.display_address
    assert "Amsterdam" in p.display_address


def test_preview_missing_data_root(tmp_path: Path) -> None:
    result = build_preview("1011AB-12", data_root=tmp_path / "nonexistent")
    assert result is None
