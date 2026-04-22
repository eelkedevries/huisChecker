"""PDOK Locatieserver client for nationwide Dutch address search.

Thin wrapper around the public Locatieserver `free` and `lookup` endpoints.
Returns typed `PdokAddress` records; network errors propagate as exceptions.

The default client is lazily instantiated and may be swapped via `set_client()`
for tests or offline runs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx

PDOK_BASE_DEFAULT = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"


def _base_url() -> str:
    return os.getenv("PDOK_LOCATIESERVER_BASE", PDOK_BASE_DEFAULT).rstrip("/")


@dataclass(frozen=True)
class PdokAddress:
    """Canonical address record resolved from PDOK Locatieserver."""

    id: str
    weergavenaam: str
    straatnaam: str
    huisnummer: str
    huisletter: str
    huisnummertoevoeging: str
    postcode: str
    woonplaatsnaam: str
    gemeentenaam: str
    gemeentecode: str
    provincienaam: str
    provinciecode: str
    adresseerbaarobject_id: str
    nummeraanduiding_id: str
    latitude: float | None
    longitude: float | None


class PdokClient(Protocol):
    def search(self, query: str, *, rows: int = 10) -> list[PdokAddress]: ...
    def lookup(self, address_id: str) -> PdokAddress | None: ...


class HttpPdokClient:
    """Real HTTP client hitting api.pdok.nl."""

    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self._base = (base_url or _base_url()).rstrip("/")
        self._timeout = timeout

    def search(self, query: str, *, rows: int = 10) -> list[PdokAddress]:
        params = {"q": query, "fq": "type:adres", "rows": str(rows)}
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self._base}/free", params=params)
            resp.raise_for_status()
        docs = resp.json().get("response", {}).get("docs", []) or []
        return [_doc_to_address(d) for d in docs]

    def lookup(self, address_id: str) -> PdokAddress | None:
        # BAG nummeraanduiding IDs are exactly 16 digits; PDOK lookup needs the
        # Solr document URN id, not the bare numeric id.
        if len(address_id) == 16 and address_id.isdigit():
            pdok_id = f"adr-NL.IMBAG.Nummeraanduiding.{address_id}"
        else:
            pdok_id = address_id
        params = {"id": pdok_id}
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self._base}/lookup", params=params)
            resp.raise_for_status()
        docs = resp.json().get("response", {}).get("docs", []) or []
        return _doc_to_address(docs[0]) if docs else None


def _doc_to_address(doc: dict) -> PdokAddress:
    lat, lon = _parse_centroide(doc.get("centroide_ll"))
    nummer_id = doc.get("nummeraanduiding_id") or doc.get("id") or ""
    return PdokAddress(
        id=nummer_id,
        weergavenaam=doc.get("weergavenaam", "") or "",
        straatnaam=doc.get("straatnaam", "") or "",
        huisnummer=str(doc.get("huisnummer", "") or ""),
        huisletter=doc.get("huisletter", "") or "",
        huisnummertoevoeging=doc.get("huisnummertoevoeging", "") or "",
        postcode=(doc.get("postcode", "") or "").replace(" ", ""),
        woonplaatsnaam=doc.get("woonplaatsnaam", "") or "",
        gemeentenaam=doc.get("gemeentenaam", "") or "",
        gemeentecode=str(doc.get("gemeentecode", "") or ""),
        provincienaam=doc.get("provincienaam", "") or "",
        provinciecode=str(doc.get("provinciecode", "") or ""),
        adresseerbaarobject_id=str(doc.get("adresseerbaarobject_id", "") or ""),
        nummeraanduiding_id=str(nummer_id),
        latitude=lat,
        longitude=lon,
    )


def _parse_centroide(raw: str | None) -> tuple[float | None, float | None]:
    if not raw or not raw.startswith("POINT("):
        return None, None
    try:
        inner = raw[len("POINT(") : -1]
        lon_str, lat_str = inner.split()
        return float(lat_str), float(lon_str)
    except (ValueError, IndexError):
        return None, None


_default_client: PdokClient | None = None


def get_client() -> PdokClient:
    global _default_client
    if _default_client is None:
        _default_client = HttpPdokClient()
    return _default_client


def set_client(client: PdokClient | None) -> None:
    """Override (or reset with None) the default PDOK client."""
    global _default_client
    _default_client = client


__all__ = [
    "HttpPdokClient",
    "PdokAddress",
    "PdokClient",
    "get_client",
    "set_client",
]
