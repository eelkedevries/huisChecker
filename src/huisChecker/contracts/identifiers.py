"""Canonical identifier types and join rules.

Join rules (precomputed, never runtime-chained):

- address -> bag_object
    match on the BAG `nummeraanduiding` key returned by PDOK address
    resolution; the resolved `verblijfsobject` id is stored on `Address`.
- address -> postcode4
    `Address.postcode[:4]`.
- postcode4 -> municipality
    CBS postcode-to-municipality lookup table (annual snapshot) stored
    as `Postcode4Area.municipality_code`.
- municipality -> province
    CBS municipality metadata stored as `Municipality.province_code`.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

_POSTCODE_RE = re.compile(r"^[1-9][0-9]{3}[A-Z]{2}$")
_POSTCODE4_RE = re.compile(r"^[1-9][0-9]{3}$")
_BAG_ID_RE = re.compile(r"^[0-9]{16}$")
_MUN_RE = re.compile(r"^GM[0-9]{4}$")
_PROV_RE = re.compile(r"^PV[0-9]{2}$")


def _normalize_postcode(value: str) -> str:
    cleaned = value.replace(" ", "").upper()
    if not _POSTCODE_RE.fullmatch(cleaned):
        raise ValueError(f"invalid Dutch postcode: {value!r}")
    return cleaned


def _check_postcode4(value: str) -> str:
    if not _POSTCODE4_RE.fullmatch(value):
        raise ValueError(f"invalid postcode4: {value!r}")
    return value


def _check_bag_id(value: str) -> str:
    if not _BAG_ID_RE.fullmatch(value):
        raise ValueError(f"invalid BAG id (expect 16 digits): {value!r}")
    return value


def _check_municipality(value: str) -> str:
    if not _MUN_RE.fullmatch(value.upper()):
        raise ValueError(f"invalid CBS municipality code: {value!r}")
    return value.upper()


def _check_province(value: str) -> str:
    if not _PROV_RE.fullmatch(value.upper()):
        raise ValueError(f"invalid CBS province code: {value!r}")
    return value.upper()


Postcode = Annotated[str, AfterValidator(_normalize_postcode)]
Postcode4 = Annotated[str, AfterValidator(_check_postcode4)]
BagObjectId = Annotated[str, AfterValidator(_check_bag_id)]
NummeraanduidingId = Annotated[str, AfterValidator(_check_bag_id)]
MunicipalityCode = Annotated[str, AfterValidator(_check_municipality)]
ProvinceCode = Annotated[str, AfterValidator(_check_province)]


def canonical_address_id(postcode: str, house_number: int, addition: str | None) -> str:
    """Deterministic address id: `{postcode}-{number}[-{addition}]`."""
    pc = _normalize_postcode(postcode)
    suffix = f"-{addition.strip().upper()}" if addition and addition.strip() else ""
    return f"{pc}-{house_number}{suffix}"


def postcode4_of(postcode: str) -> str:
    return _normalize_postcode(postcode)[:4]


__all__ = [
    "BagObjectId",
    "MunicipalityCode",
    "NummeraanduidingId",
    "Postcode",
    "Postcode4",
    "ProvinceCode",
    "canonical_address_id",
    "postcode4_of",
]
