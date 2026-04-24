"""Authoritative postcode4 geometry loader.

Layer-producing ETL jobs (Leefbaarometer, CBS density, Klimaat) resolve
PC4 polygons via the bundled authoritative boundaries file
``src/huisChecker/etl/fixtures/pc4_boundaries.geojson``. Shapes are
irregular, multi-vertex polygons derived from PDOK / CBS PC4 boundary
data, simplified for MVP scope. The file ships with the repo so a
fresh checkout renders real PC4 polygons without an ETL rerun. A PC4
missing from the file falls back to a nil-island point; the map layer
surfaces that explicitly instead of painting a bounding-box overlay.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "pc4_boundaries.geojson"
)


@lru_cache(maxsize=4)
def _load(path_str: str) -> dict[str, dict[str, Any]]:
    path = Path(path_str)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for feature in payload.get("features", []):
        pc4 = str((feature.get("properties") or {}).get("postcode4") or "").strip()
        geom = feature.get("geometry")
        if pc4 and isinstance(geom, dict):
            out[pc4] = geom
    return out


def pc4_geometry(pc4: str, *, geometry_path: Path | None = None) -> dict[str, Any]:
    """Return the authoritative geometry for ``pc4``.

    Falls back to a Point at (0, 0) when the PC4 is not in the curated
    boundary file. The JS overlay treats nil-island points as "data
    present but geometry unavailable" and surfaces that explicitly.
    """
    path = geometry_path or _DEFAULT_PATH
    table = _load(str(path))
    geom = table.get(pc4)
    if geom is None:
        return {"type": "Point", "coordinates": [0.0, 0.0]}
    # Return a deep-enough copy so caller can mutate without affecting cache.
    return json.loads(json.dumps(geom))


def pc4_feature(
    pc4: str,
    properties: dict[str, Any],
    *,
    geometry_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": pc4_geometry(pc4, geometry_path=geometry_path),
    }


def available_pc4s(*, geometry_path: Path | None = None) -> tuple[str, ...]:
    path = geometry_path or _DEFAULT_PATH
    return tuple(sorted(_load(str(path)).keys()))


# --- Back-compat shims ------------------------------------------------------
# Older call sites used ``pc4_polygon_feature`` / ``pc4_polygon_coordinates``
# (rectangle stubs). Keep the names so a grep for the old API works while
# routing them through the authoritative loader.


def pc4_polygon_feature(pc4: str, properties: dict[str, Any]) -> dict[str, Any]:
    return pc4_feature(pc4, properties)


def pc4_polygon_coordinates(pc4: str) -> list[list[list[float]]]:
    geom = pc4_geometry(pc4)
    if geom.get("type") == "Polygon":
        return geom["coordinates"]  # type: ignore[no-any-return]
    return [[[0.0, 0.0]]]


__all__ = [
    "available_pc4s",
    "pc4_feature",
    "pc4_geometry",
    "pc4_polygon_coordinates",
    "pc4_polygon_feature",
]
