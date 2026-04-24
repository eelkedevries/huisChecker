"""Leefbaarometer adapter.

Remote Leefbaarometer access is awkward (portal-driven, not a stable
API for per-PC4 pulls). The adapter therefore deliberately sticks to a
minimal local subset for in-scope pc4s / municipalities / provinces.

When the curated CSV carries the five official Leefbaarometer 3.0
dimension scores they are returned alongside the overall score; when a
PC4 only has the overall score the `dimensions` key is empty so the UI
can state that clearly instead of implying full dimension support.
"""

from __future__ import annotations

import os
from pathlib import Path

from huisChecker.etl.io import read_csv
from huisChecker.etl.sources.leefbaarometer import DIMENSION_KEYS

ADAPTER = "leefbaarometer"


def fetch_pc4(pc4: str, *, data_root: Path | None = None) -> dict | None:
    if not pc4:
        return None
    return _load_subset(pc4, data_root=data_root)


def _load_subset(pc4: str, *, data_root: Path | None = None) -> dict | None:
    root = data_root if data_root is not None else Path(os.getenv("DATA_DIR", "data"))
    path = root / "curated" / "leefbaarometer_pc4.csv"
    if not path.exists():
        return None
    for row in read_csv(path):
        if row.get("postcode4") == pc4:
            dims: dict[str, str] = {}
            for key in DIMENSION_KEYS:
                value = (row.get(key) or "").strip()
                if value:
                    dims[key] = value
            return {
                "postcode4": pc4,
                "score": row.get("score") or None,
                "band": row.get("band") or None,
                "reference_period": row.get("reference_period", ""),
                "dimensions": dims,
                "source": "lokale subset (Leefbaarometer)",
            }
    return None


__all__ = ["ADAPTER", "DIMENSION_KEYS", "fetch_pc4"]
