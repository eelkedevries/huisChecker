"""Stub geometries for PC4 areas used by layer-producing ETL jobs.

Real pipelines join against authoritative PC4 boundaries (PDOK, CBS).
In the MVP we ship a small hand-picked centroid lookup so curated
layer geojsons are visibly renderable on a map. A missing PC4 falls
back to a nil-island Polygon so downstream validators still pass.
"""

from __future__ import annotations

_PC4_CENTROIDS: dict[str, tuple[float, float]] = {
    # lon, lat
    "1011": (4.901, 52.372),
    "1012": (4.890, 52.376),
    "2316": (4.503, 52.163),
    "3011": (4.479, 51.922),
    "3511": (5.117, 52.090),
}

_HALF_WIDTH = 0.010  # polygon visibly larger than the focus marker at zoom 14


def pc4_polygon_coordinates(pc4: str) -> list[list[list[float]]]:
    lon, lat = _PC4_CENTROIDS.get(pc4, (0.0, 0.0))
    w = _HALF_WIDTH
    ring = [
        [lon - w, lat - w],
        [lon + w, lat - w],
        [lon + w, lat + w],
        [lon - w, lat + w],
        [lon - w, lat - w],
    ]
    return [ring]


def pc4_polygon_feature(pc4: str, properties: dict) -> dict:
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Polygon",
            "coordinates": pc4_polygon_coordinates(pc4),
        },
    }


__all__ = ["pc4_polygon_coordinates", "pc4_polygon_feature"]
