"""Klimaateffectatlas / Atlas Leefomgeving adapter.

Map overlays are rendered remotely from a WMS/WMTS endpoint where
possible so the app does not need a national raster download. The
adapter also returns per-pc4 class labels cached from the KEA
service; if unavailable, falls back to the curated subset.
"""

from __future__ import annotations

import os
from pathlib import Path

from huisChecker.etl.io import read_csv
from huisChecker.remote.cache import cache_get
from huisChecker.scope import current_scope

ADAPTER = "klimaat"

KEA_WMS_DEFAULT = "https://service.pdok.nl/rws/klimaateffectatlas/wms/v1_0"
KEA_FLOOD_LAYER_DEFAULT = "overstromingskans_2050"


def wms_config() -> dict:
    """Remote tile config used by the map partial + layer registry."""
    return {
        "url": os.getenv("KEA_WMS_URL", KEA_WMS_DEFAULT),
        "flood_layer": os.getenv("KEA_FLOOD_LAYER", KEA_FLOOD_LAYER_DEFAULT),
        "attribution": "Klimaateffectatlas (CAS)",
    }


def fetch_pc4(pc4: str, *, data_root: Path | None = None) -> dict | None:
    if not pc4:
        return None
    if current_scope().contains_pc4(pc4):
        cached = cache_get(ADAPTER, pc4)
        if cached:
            return cached
    return _fallback_curated(pc4, data_root=data_root)


def _fallback_curated(pc4: str, *, data_root: Path | None = None) -> dict | None:
    root = data_root if data_root is not None else Path(os.getenv("DATA_DIR", "data"))
    path = root / "curated" / "klimaat_pc4.csv"
    if not path.exists():
        return None
    for row in read_csv(path):
        if row.get("postcode4") == pc4:
            return {
                "postcode4": pc4,
                "flood_probability_class": row.get("flood_probability_class") or None,
                "heat_stress_class": row.get("heat_stress_class") or None,
                "road_noise_class": row.get("road_noise_class") or None,
                "reference_period": row.get("reference_period", ""),
                "source": "lokale subset (Klimaateffectatlas / Atlas Leefomgeving)",
            }
    return None


__all__ = ["ADAPTER", "fetch_pc4", "wms_config"]
