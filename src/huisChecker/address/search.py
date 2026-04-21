"""Address text search over curated BAG fixture data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from huisChecker.etl.io import read_csv


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


def _default_curated_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "curated"


def _make_display(row: dict[str, str]) -> str:
    addr = f"{row['street']} {row['house_number']}"
    if row.get("house_number_addition"):
        addr += f" {row['house_number_addition']}"
    return f"{addr}, {row['city']} ({row['postcode']})"


def search_addresses(
    query: str, curated_root: Path | None = None
) -> list[AddressCandidate]:
    """Return up to 10 candidates where every query token appears in the address string."""
    root = curated_root if curated_root is not None else _default_curated_root()
    path = root / "addresses.csv"
    if not path.exists():
        return []

    tokens = [t for t in re.split(r"[\s,\-]+", query.strip().lower()) if t]
    if not tokens:
        return []

    results: list[AddressCandidate] = []
    for row in read_csv(path):
        haystack = " ".join(
            [
                row.get("street", ""),
                row.get("house_number", ""),
                row.get("house_number_addition", ""),
                row.get("city", ""),
                row.get("postcode", ""),
                row.get("postcode4", ""),
            ]
        ).lower()
        if all(t in haystack for t in tokens):
            results.append(
                AddressCandidate(
                    id=row["id"],
                    display=_make_display(row),
                    street=row["street"],
                    house_number=row["house_number"],
                    house_number_addition=row.get("house_number_addition", ""),
                    city=row["city"],
                    postcode=row["postcode"],
                    postcode4=row["postcode4"],
                    municipality_code=row["municipality_code"],
                    province_code=row["province_code"],
                )
            )
    return results[:10]


def get_address_row(address_id: str, curated_root: Path | None = None) -> dict[str, str] | None:
    root = curated_root if curated_root is not None else _default_curated_root()
    path = root / "addresses.csv"
    if not path.exists():
        return None
    for row in read_csv(path):
        if row["id"] == address_id:
            return row
    return None


__all__ = ["AddressCandidate", "get_address_row", "search_addresses"]
