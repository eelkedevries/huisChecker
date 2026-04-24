"""BAG building-attribute adapter.

Resolution itself already runs live via `address.pdok`. This adapter
layers on top to fetch building attributes (construction year,
surface, use purpose) for the selected address via the PDOK BAG
endpoints when possible. No nationwide BAG ingest.
"""

from __future__ import annotations

import os
from pathlib import Path

from huisChecker.etl.io import read_csv
from huisChecker.remote.cache import cache_get, cache_put

ADAPTER = "bag"


def _timeout() -> float:
    try:
        return float(os.getenv("REMOTE_TIMEOUT_SECONDS", "4"))
    except ValueError:
        return 4.0


def fetch_object(bag_object_id: str, *, data_root: Path | None = None) -> dict | None:
    if not bag_object_id:
        return None
    cached = cache_get(ADAPTER, bag_object_id)
    if cached:
        return cached
    live = _fetch_live(bag_object_id)
    if live:
        cache_put(ADAPTER, bag_object_id, live)
        return live
    return _fallback_curated(bag_object_id, data_root=data_root)


def _fetch_live(bag_object_id: str) -> dict | None:
    base = os.getenv("BAG_BASE_URL", "").rstrip("/")
    if not base:
        return None
    try:
        import httpx
    except Exception:
        return None
    try:
        with httpx.Client(timeout=_timeout()) as client:
            resp = client.get(f"{base}/verblijfsobject/{bag_object_id}")
            resp.raise_for_status()
        data = resp.json() or {}
    except Exception:
        return None
    return {
        "id": bag_object_id,
        "construction_year": data.get("oorspronkelijkBouwjaar") or data.get("construction_year"),
        "surface_area_m2": data.get("oppervlakte") or data.get("surface_area_m2"),
        "use_purpose": ";".join(data.get("gebruiksdoelen") or []) or data.get("use_purpose"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "source": "PDOK BAG",
    }


def _fallback_curated(bag_object_id: str, *, data_root: Path | None = None) -> dict | None:
    root = data_root if data_root is not None else Path(os.getenv("DATA_DIR", "data"))
    path = root / "curated" / "bag_objects.csv"
    if not path.exists():
        return None
    for row in read_csv(path):
        if row.get("id") == bag_object_id:
            return {
                "id": bag_object_id,
                "construction_year": row.get("construction_year"),
                "surface_area_m2": row.get("surface_area_m2"),
                "use_purpose": row.get("use_purpose"),
                "latitude": _to_float(row.get("latitude")),
                "longitude": _to_float(row.get("longitude")),
                "source": "lokale subset (BAG)",
            }
    return None


def _to_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


__all__ = ["ADAPTER", "fetch_object"]
