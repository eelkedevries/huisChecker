"""SQLite cache of PDOK-resolved addresses.

Stores the canonical identifiers needed for local enrichment (BAG object id,
postcode4, municipality/province codes and names, lat/lon). Keyed by the
nummeraanduiding id used as the public address id across the app.
"""

from __future__ import annotations

from dataclasses import dataclass

from huisChecker.db import get_conn


@dataclass(frozen=True)
class ResolvedAddress:
    address_id: str
    nummeraanduiding_id: str
    bag_object_id: str
    postcode: str
    street: str
    house_number: str
    house_number_addition: str
    city: str
    postcode4: str
    municipality_code: str
    municipality_name: str
    province_code: str
    province_name: str
    latitude: float | None
    longitude: float | None


def _row_to_resolved(row) -> ResolvedAddress:
    return ResolvedAddress(
        address_id=row["address_id"],
        nummeraanduiding_id=row["nummeraanduiding_id"] or "",
        bag_object_id=row["bag_object_id"] or "",
        postcode=row["postcode"] or "",
        street=row["street"] or "",
        house_number=row["house_number"] or "",
        house_number_addition=row["house_number_addition"] or "",
        city=row["city"] or "",
        postcode4=row["postcode4"] or "",
        municipality_code=row["municipality_code"] or "",
        municipality_name=row["municipality_name"] or "",
        province_code=row["province_code"] or "",
        province_name=row["province_name"] or "",
        latitude=row["latitude"],
        longitude=row["longitude"],
    )


def get_resolved(address_id: str) -> ResolvedAddress | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM resolved_addresses WHERE address_id = ?", (address_id,)
        )
        row = cur.fetchone()
    return _row_to_resolved(row) if row else None


def store_resolved(addr: ResolvedAddress) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO resolved_addresses (
                address_id, nummeraanduiding_id, bag_object_id, postcode,
                street, house_number, house_number_addition, city, postcode4,
                municipality_code, municipality_name, province_code, province_name,
                latitude, longitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                addr.address_id,
                addr.nummeraanduiding_id,
                addr.bag_object_id,
                addr.postcode,
                addr.street,
                addr.house_number,
                addr.house_number_addition,
                addr.city,
                addr.postcode4,
                addr.municipality_code,
                addr.municipality_name,
                addr.province_code,
                addr.province_name,
                addr.latitude,
                addr.longitude,
            ),
        )


__all__ = ["ResolvedAddress", "get_resolved", "store_resolved"]
