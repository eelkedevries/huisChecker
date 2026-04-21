"""Tests for address text search over curated fixture data."""

from __future__ import annotations

from pathlib import Path

import pytest

from huisChecker.address.search import AddressCandidate, get_address_row, search_addresses
from huisChecker.etl.base import JobContext, SourceMode
from huisChecker.etl.pipeline import run_smoke


@pytest.fixture(scope="module")
def curated_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("data")
    data_root = tmp / "data"
    fixtures = Path(__file__).resolve().parents[1] / "src/huisChecker/etl/fixtures"
    ctx = JobContext(
        data_root=data_root,
        curated_root=data_root / "curated",
        manifests_root=data_root / "manifests",
        fixtures_root=fixtures,
        mode=SourceMode.FIXTURE,
    )
    run_smoke(ctx)
    return ctx.curated_root


def test_search_by_street_returns_match(curated_root: Path) -> None:
    results = search_addresses("Damrak", curated_root=curated_root)
    assert len(results) == 1
    assert results[0].id == "1011AB-12"
    assert results[0].city == "Amsterdam"


def test_search_by_street_and_city(curated_root: Path) -> None:
    results = search_addresses("Coolsingel Rotterdam", curated_root=curated_root)
    assert len(results) == 1
    assert results[0].postcode4 == "3011"


def test_search_by_postcode_and_number(curated_root: Path) -> None:
    results = search_addresses("3511AB 7", curated_root=curated_root)
    assert len(results) == 1
    assert results[0].id == "3511AB-7"


def test_search_with_addition(curated_root: Path) -> None:
    results = search_addresses("Nieuwendijk 5 A Amsterdam", curated_root=curated_root)
    assert len(results) == 1
    assert results[0].id == "1012AB-5-A"
    assert results[0].house_number_addition == "A"


def test_search_by_city_returns_multiple(curated_root: Path) -> None:
    results = search_addresses("Amsterdam", curated_root=curated_root)
    assert len(results) == 2
    ids = {r.id for r in results}
    assert "1011AB-12" in ids
    assert "1012AB-5-A" in ids


def test_search_empty_query_returns_empty(curated_root: Path) -> None:
    assert search_addresses("", curated_root=curated_root) == []
    assert search_addresses("   ", curated_root=curated_root) == []


def test_search_no_match_returns_empty(curated_root: Path) -> None:
    results = search_addresses("Nonexistent Street 999", curated_root=curated_root)
    assert results == []


def test_search_result_is_candidate(curated_root: Path) -> None:
    results = search_addresses("Oudegracht", curated_root=curated_root)
    assert len(results) == 1
    c = results[0]
    assert isinstance(c, AddressCandidate)
    assert c.municipality_code == "GM0344"
    assert c.province_code == "PV26"
    assert "Oudegracht" in c.display


def test_search_hyphenated_id_format(curated_root: Path) -> None:
    results = search_addresses("1011AB-12", curated_root=curated_root)
    assert len(results) == 1
    assert results[0].id == "1011AB-12"


def test_get_address_row_found(curated_root: Path) -> None:
    row = get_address_row("3011AB-42", curated_root=curated_root)
    assert row is not None
    assert row["street"] == "Coolsingel"
    assert row["city"] == "Rotterdam"


def test_get_address_row_not_found(curated_root: Path) -> None:
    row = get_address_row("9999ZZ-0", curated_root=curated_root)
    assert row is None


def test_search_missing_curated_dir(tmp_path: Path) -> None:
    results = search_addresses("Damrak", curated_root=tmp_path / "nonexistent")
    assert results == []
