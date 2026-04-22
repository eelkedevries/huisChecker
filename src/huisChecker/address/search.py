"""Nationwide address search backed by PDOK Locatieserver.

Free-text queries hit PDOK and return candidate nummeraanduiding records.
Selecting a candidate resolves the canonical identifiers needed for local
enrichment (BAG object id, postcode4, municipality/province codes, lat/lon)
and persists them in the SQLite cache so follow-up views are offline.
"""

from __future__ import annotations

from dataclasses import dataclass

from huisChecker.address.cache import ResolvedAddress, get_resolved, store_resolved
from huisChecker.address.pdok import PdokAddress, PdokClient, get_client


@dataclass(frozen=True)
class AddressCandidate:
    id: str
    display: str
    street: str
    house_number: str
    house_number_addition: str
    city: str
    postcode: str
    postcode4: str
    municipality_code: str
    province_code: str


def _normalise_municipality_code(code: str) -> str:
    code = (code or "").strip()
    if not code:
        return ""
    if code.upper().startswith("GM"):
        return code.upper()
    return f"GM{code.zfill(4)}"


def _normalise_province_code(code: str) -> str:
    code = (code or "").strip()
    if not code:
        return ""
    if code.upper().startswith("PV"):
        return code.upper()
    return f"PV{code}"


def _postcode4(postcode: str) -> str:
    pc = (postcode or "").replace(" ", "")
    return pc[:4] if len(pc) >= 4 else pc


def _display(addr: PdokAddress) -> str:
    if addr.weergavenaam:
        return addr.weergavenaam
    parts = [addr.straatnaam, addr.huisnummer]
    suffix = (addr.huisletter + addr.huisnummertoevoeging).strip()
    if suffix:
        parts.append(suffix)
    base = " ".join(p for p in parts if p)
    return f"{base}, {addr.postcode} {addr.woonplaatsnaam}".strip()


def _pdok_to_candidate(addr: PdokAddress) -> AddressCandidate:
    return AddressCandidate(
        id=addr.id,
        display=_display(addr),
        street=addr.straatnaam,
        house_number=addr.huisnummer,
        house_number_addition=(addr.huisletter + addr.huisnummertoevoeging).strip(),
        city=addr.woonplaatsnaam,
        postcode=addr.postcode,
        postcode4=_postcode4(addr.postcode),
        municipality_code=_normalise_municipality_code(addr.gemeentecode),
        province_code=_normalise_province_code(addr.provinciecode),
    )


def _pdok_to_resolved(addr: PdokAddress) -> ResolvedAddress:
    return ResolvedAddress(
        address_id=addr.id,
        nummeraanduiding_id=addr.nummeraanduiding_id or addr.id,
        bag_object_id=addr.adresseerbaarobject_id,
        postcode=addr.postcode,
        street=addr.straatnaam,
        house_number=addr.huisnummer,
        house_number_addition=(addr.huisletter + addr.huisnummertoevoeging).strip(),
        city=addr.woonplaatsnaam,
        postcode4=_postcode4(addr.postcode),
        municipality_code=_normalise_municipality_code(addr.gemeentecode),
        municipality_name=addr.gemeentenaam,
        province_code=_normalise_province_code(addr.provinciecode),
        province_name=addr.provincienaam,
        latitude=addr.latitude,
        longitude=addr.longitude,
    )


def search_addresses(
    query: str, *, client: PdokClient | None = None
) -> list[AddressCandidate]:
    """Return up to 10 candidate addresses from PDOK Locatieserver."""
    if not query or not query.strip():
        return []
    pdok = client or get_client()
    try:
        hits = pdok.search(query.strip(), rows=10)
    except Exception:
        return []
    return [_pdok_to_candidate(a) for a in hits]


def resolve_address(
    address_id: str, *, client: PdokClient | None = None
) -> ResolvedAddress | None:
    """Return a resolved address, using the SQLite cache where possible."""
    if not address_id:
        return None
    cached = get_resolved(address_id)
    if cached is not None:
        return cached
    pdok = client or get_client()
    try:
        addr = pdok.lookup(address_id)
    except Exception:
        return None
    if addr is None:
        return None
    resolved = _pdok_to_resolved(addr)
    try:
        store_resolved(resolved)
    except Exception:
        pass
    return resolved


__all__ = [
    "AddressCandidate",
    "ResolvedAddress",
    "resolve_address",
    "search_addresses",
]
