"""Tests for PDOK-backed address search and resolver."""

from __future__ import annotations

from huisChecker.address.cache import get_resolved
from huisChecker.address.search import (
    AddressCandidate,
    resolve_address,
    search_addresses,
)


def test_search_by_street_returns_match() -> None:
    results = search_addresses("Damrak")
    assert any(c.id == "0363200000123456" for c in results)
    hit = next(c for c in results if c.id == "0363200000123456")
    assert hit.city == "Amsterdam"


def test_search_by_street_and_city() -> None:
    results = search_addresses("Coolsingel Rotterdam")
    assert len(results) == 1
    assert results[0].postcode4 == "3011"


def test_search_by_postcode_and_number() -> None:
    results = search_addresses("3511AB 7")
    assert len(results) == 1
    assert results[0].id == "0344200000123459"


def test_search_with_addition() -> None:
    results = search_addresses("Nieuwendijk 5 A Amsterdam")
    assert len(results) == 1
    assert results[0].id == "0363200000123457"
    assert results[0].house_number_addition == "A"


def test_search_by_city_returns_multiple() -> None:
    results = search_addresses("Amsterdam")
    ids = {r.id for r in results}
    assert "0363200000123456" in ids
    assert "0363200000123457" in ids


def test_search_nationwide_leiden_resolves() -> None:
    results = search_addresses("Breestraat Leiden")
    assert len(results) == 1
    assert results[0].id == "0546200000999999"
    assert results[0].city == "Leiden"


def test_search_empty_query_returns_empty() -> None:
    assert search_addresses("") == []
    assert search_addresses("   ") == []


def test_search_no_match_returns_empty() -> None:
    assert search_addresses("Nonexistent Street 999") == []


def test_search_result_is_candidate() -> None:
    results = search_addresses("Oudegracht")
    assert len(results) == 1
    c = results[0]
    assert isinstance(c, AddressCandidate)
    assert c.municipality_code == "GM0344"
    assert c.province_code == "PV26"
    assert "Oudegracht" in c.display


def test_resolve_address_persists_canonical_identifiers() -> None:
    resolved = resolve_address("0363200000123456")
    assert resolved is not None
    assert resolved.nummeraanduiding_id == "0363200000123456"
    assert resolved.bag_object_id == "0363010000123456"
    assert resolved.postcode4 == "1011"
    assert resolved.municipality_code == "GM0363"
    assert resolved.municipality_name == "Amsterdam"
    assert resolved.province_code == "PV27"
    assert resolved.province_name == "Noord-Holland"
    assert resolved.latitude is not None and resolved.longitude is not None

    # second call hits the SQLite cache
    cached = get_resolved("0363200000123456")
    assert cached is not None
    assert cached.bag_object_id == resolved.bag_object_id


def test_resolve_address_unknown_returns_none() -> None:
    assert resolve_address("9999ZZ-0") is None


def test_resolve_address_empty_returns_none() -> None:
    assert resolve_address("") is None


def test_search_warms_sqlite_cache() -> None:
    """search_addresses populates SQLite so preview works without a second lookup."""
    results = search_addresses("Damrak Amsterdam")
    assert results
    cached = get_resolved(results[0].id)
    assert cached is not None
    assert cached.city == results[0].city
    assert cached.postcode4 == results[0].postcode4


def test_search_warms_cache_for_all_candidates() -> None:
    results = search_addresses("Amsterdam")
    assert len(results) >= 2
    for c in results:
        assert get_resolved(c.id) is not None
