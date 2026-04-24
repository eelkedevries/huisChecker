"""Authoritative postcode4 polygon source.

One table, one geometry per PC4, topologically-correct tiling: each PC4
is placed on a pointy-top hexagonal grid indexed by a ``(cluster, q, r)``
axial coordinate. Adjacent PC4s share edges by construction, so the
overlay behaves like a proper PC4 choropleth (no overlap, no gaps).

The bundled fixture ``fixtures/pc4_boundaries.geojson`` is a derived
artefact written from this table (see ``build_pc4_feature_collection``).
``_load`` recomputes from the table, so the runtime stays consistent
even if the fixture drifts on disk.

CRS: WGS84 (EPSG:4326), lon/lat in that order, matching Leaflet /
GeoJSON defaults used by the rest of the app.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "pc4_boundaries.geojson"
)

# Hex size in degrees. ~0.008° ≈ 560–900 m in NL; visually comparable to
# a real PC4 footprint at city zoom levels.
HEX_SIZE_DEG = 0.008

# Cluster centres (first two PC4 digits → nominal centre lon/lat).
CLUSTER_CENTERS: dict[str, tuple[float, float]] = {
    "10": (4.900, 52.373),  # Amsterdam centrum
    "23": (4.493, 52.158),  # Leiden
    "30": (4.479, 51.921),  # Rotterdam Feijenoord
    "35": (5.117, 52.090),  # Utrecht
}

# Axial (q, r) offsets per PC4, scoped by cluster. Every entry must be
# unique within its cluster; that guarantees non-overlapping hexes.
PC4_AXIAL: dict[str, tuple[str, int, int]] = {
    # Amsterdam
    "1011": ("10", 0, 0),
    "1012": ("10", -1, 0),
    # Rotterdam
    "3011": ("30", 0, 0),
    # Utrecht
    "3511": ("35", 0, 0),
    # Leiden: compact 10-cell cluster around the station area.
    "2311": ("23", 0, 0),
    "2312": ("23", 1, 0),
    "2313": ("23", 1, -1),
    "2314": ("23", 0, -1),
    "2315": ("23", -1, 0),
    "2316": ("23", 0, 1),
    "2317": ("23", 1, 1),
    "2318": ("23", 2, 0),
    "2321": ("23", -1, 1),
    "2322": ("23", -1, 2),
}


def _axial_to_pixel(q: int, r: int, size: float) -> tuple[float, float]:
    # Pointy-top axial → planar offset from cluster centre.
    dx = size * math.sqrt(3.0) * (q + r / 2.0)
    dy = size * 1.5 * r
    return dx, dy


def _hex_ring(cx: float, cy: float, size: float) -> list[list[float]]:
    # Pointy-top vertices, clockwise, closed ring. Rounded to keep JSON
    # and downstream equality checks stable.
    s32 = size * math.sqrt(3.0) / 2.0
    verts = [
        (cx,           cy + size),
        (cx + s32,     cy + size / 2.0),
        (cx + s32,     cy - size / 2.0),
        (cx,           cy - size),
        (cx - s32,     cy - size / 2.0),
        (cx - s32,     cy + size / 2.0),
    ]
    ring = [[round(x, 6), round(y, 6)] for x, y in verts]
    ring.append(ring[0])
    return ring


def build_pc4_feature_collection() -> dict[str, Any]:
    """Authoritative PC4 polygon layer, built from the axial table."""
    features: list[dict[str, Any]] = []
    for pc4 in sorted(PC4_AXIAL):
        cluster, q, r = PC4_AXIAL[pc4]
        cx_base, cy_base = CLUSTER_CENTERS[cluster]
        dx, dy = _axial_to_pixel(q, r, HEX_SIZE_DEG)
        ring = _hex_ring(cx_base + dx, cy_base + dy, HEX_SIZE_DEG)
        features.append(
            {
                "type": "Feature",
                "properties": {"postcode4": pc4},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    return {"type": "FeatureCollection", "crs": "EPSG:4326", "features": features}


@lru_cache(maxsize=1)
def _built_table() -> dict[str, dict[str, Any]]:
    fc = build_pc4_feature_collection()
    return {
        f["properties"]["postcode4"]: f["geometry"] for f in fc["features"]
    }


@lru_cache(maxsize=4)
def _load(path_str: str) -> dict[str, dict[str, Any]]:
    # Retained for back-compat with callers that pass an explicit
    # geometry_path. Default path reads from the in-memory table so the
    # on-disk fixture can't drift into an authoritative position.
    if path_str == str(_DEFAULT_PATH):
        return _built_table()
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

    Falls back to a nil-island Point when the PC4 is not registered.
    The JS overlay surfaces that as "data present but geometry
    unavailable" rather than painting a misleading shape.
    """
    path = geometry_path or _DEFAULT_PATH
    table = _load(str(path))
    geom = table.get(pc4)
    if geom is None:
        return {"type": "Point", "coordinates": [0.0, 0.0]}
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


def write_default_fixture(path: Path | None = None) -> Path:
    """Regenerate the on-disk fixture from the axial table."""
    target = path or _DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_pc4_feature_collection(), indent=2) + "\n",
        encoding="utf-8",
    )
    return target


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
    return [[[0.0, 0.0]]]


__all__ = [
    "CLUSTER_CENTERS",
    "HEX_SIZE_DEG",
    "PC4_AXIAL",
    "available_pc4s",
    "build_pc4_feature_collection",
    "pc4_feature",
    "pc4_geometry",
    "pc4_polygon_coordinates",
    "pc4_polygon_feature",
    "write_default_fixture",
]
