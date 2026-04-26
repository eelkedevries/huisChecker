"""Authoritative postcode4 polygon source.

The bundled fixture ``fixtures/pc4_boundaries.geojson`` is a real subset
of the CBS PC4 boundaries (PDOK WFS service, dataset
``cbs/postcode4/2024``, attribution: © CBS / Kadaster, CC-BY 4.0). One
feature per PC4, geometry as published — including MultiPolygon and
holes — so the overlay matches the actual administrative areas.

CRS: WGS84 (EPSG:4326), lon/lat order, matching Leaflet / GeoJSON
defaults used by the rest of the app.

The module name is historical (it used to ship hex-grid stubs); the
loader is now authoritative. Geometry is loaded once from the fixture
and cached.
"""

from __future__ import annotations

import json
from copy import deepcopy
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

    Falls back to a nil-island Point when the PC4 is not in the boundary
    table. The JS overlay surfaces that as "data present but geometry
    unavailable" rather than painting a misleading shape.
    """
    path = geometry_path or _DEFAULT_PATH
    table = _load(str(path))
    geom = table.get(pc4)
    if geom is None:
        return {"type": "Point", "coordinates": [0.0, 0.0]}
    return deepcopy(geom)


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
# when the stubs were rectangles. Route them through the authoritative
# loader so a grep for the old API still works.


def pc4_polygon_feature(pc4: str, properties: dict[str, Any]) -> dict[str, Any]:
    return pc4_feature(pc4, properties)


def pc4_polygon_coordinates(pc4: str) -> list[list[list[float]]]:
    geom = pc4_geometry(pc4)
    if geom.get("type") == "Polygon":
        return geom["coordinates"]  # type: ignore[no-any-return]
    if geom.get("type") == "MultiPolygon":
        # Return the first polygon's rings for back-compat callers that
        # expected a Polygon-shaped coordinate stack.
        return geom["coordinates"][0]  # type: ignore[no-any-return]
    return [[[0.0, 0.0]]]


__all__ = [
    "available_pc4s",
    "pc4_feature",
    "pc4_geometry",
    "pc4_polygon_coordinates",
    "pc4_polygon_feature",
]
