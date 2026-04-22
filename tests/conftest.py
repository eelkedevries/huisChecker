"""Shared test fixtures.

Installs a fake PDOK Locatieserver client and isolates the SQLite cache per
test so the suite runs offline and without mutating the project data dir.
"""

from __future__ import annotations

import pytest

from huisChecker.address import pdok
from huisChecker.address.pdok import PdokAddress

FIXTURE_PDOK_ADDRESSES: dict[str, PdokAddress] = {
    "0363200000123456": PdokAddress(
        id="0363200000123456",
        weergavenaam="Damrak 12, 1011AB Amsterdam",
        straatnaam="Damrak",
        huisnummer="12",
        huisletter="",
        huisnummertoevoeging="",
        postcode="1011AB",
        woonplaatsnaam="Amsterdam",
        gemeentenaam="Amsterdam",
        gemeentecode="0363",
        provincienaam="Noord-Holland",
        provinciecode="27",
        adresseerbaarobject_id="0363010000123456",
        nummeraanduiding_id="0363200000123456",
        latitude=52.3746,
        longitude=4.8998,
    ),
    "0363200000123457": PdokAddress(
        id="0363200000123457",
        weergavenaam="Nieuwendijk 5 A, 1012AB Amsterdam",
        straatnaam="Nieuwendijk",
        huisnummer="5",
        huisletter="A",
        huisnummertoevoeging="",
        postcode="1012AB",
        woonplaatsnaam="Amsterdam",
        gemeentenaam="Amsterdam",
        gemeentecode="0363",
        provincienaam="Noord-Holland",
        provinciecode="27",
        adresseerbaarobject_id="0363010000123457",
        nummeraanduiding_id="0363200000123457",
        latitude=52.3755,
        longitude=4.8935,
    ),
    "0599200000123458": PdokAddress(
        id="0599200000123458",
        weergavenaam="Coolsingel 42, 3011AB Rotterdam",
        straatnaam="Coolsingel",
        huisnummer="42",
        huisletter="",
        huisnummertoevoeging="",
        postcode="3011AB",
        woonplaatsnaam="Rotterdam",
        gemeentenaam="Rotterdam",
        gemeentecode="0599",
        provincienaam="Zuid-Holland",
        provinciecode="28",
        adresseerbaarobject_id="0599010000123458",
        nummeraanduiding_id="0599200000123458",
        latitude=51.9225,
        longitude=4.4792,
    ),
    "0344200000123459": PdokAddress(
        id="0344200000123459",
        weergavenaam="Oudegracht 7, 3511AB Utrecht",
        straatnaam="Oudegracht",
        huisnummer="7",
        huisletter="",
        huisnummertoevoeging="",
        postcode="3511AB",
        woonplaatsnaam="Utrecht",
        gemeentenaam="Utrecht",
        gemeentecode="0344",
        provincienaam="Utrecht",
        provinciecode="26",
        adresseerbaarobject_id="0344010000123459",
        nummeraanduiding_id="0344200000123459",
        latitude=52.0907,
        longitude=5.1214,
    ),
    # Leiden: present in PDOK but outside the local curated enrichment.
    "0546200000999999": PdokAddress(
        id="0546200000999999",
        weergavenaam="Breestraat 1, 2311CH Leiden",
        straatnaam="Breestraat",
        huisnummer="1",
        huisletter="",
        huisnummertoevoeging="",
        postcode="2311CH",
        woonplaatsnaam="Leiden",
        gemeentenaam="Leiden",
        gemeentecode="0546",
        provincienaam="Zuid-Holland",
        provinciecode="28",
        adresseerbaarobject_id="0546010000999999",
        nummeraanduiding_id="0546200000999999",
        latitude=52.1597,
        longitude=4.4892,
    ),
}


class FakePdokClient:
    def __init__(self, addresses: dict[str, PdokAddress] | None = None) -> None:
        self._addresses = addresses or FIXTURE_PDOK_ADDRESSES

    def search(self, query: str, *, rows: int = 10) -> list[PdokAddress]:
        q = (query or "").lower().strip()
        if not q:
            return []
        tokens = [t for t in q.replace(",", " ").split() if t]
        matches: list[PdokAddress] = []
        for a in self._addresses.values():
            hay = " ".join(
                [
                    a.straatnaam,
                    a.huisnummer,
                    a.huisletter,
                    a.huisnummertoevoeging,
                    a.postcode,
                    a.woonplaatsnaam,
                    a.weergavenaam,
                    a.nummeraanduiding_id,
                ]
            ).lower()
            if all(t in hay for t in tokens):
                matches.append(a)
        return matches[:rows]

    def lookup(self, address_id: str) -> PdokAddress | None:
        return self._addresses.get(address_id)


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Per-test isolated DATA_DIR and fake PDOK client."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from huisChecker.db import init_db

    init_db()
    pdok.set_client(FakePdokClient())
    try:
        yield
    finally:
        pdok.set_client(None)
