"""Map layer service: load curated geojson, enrich with styling, build payloads.

Templates and routes depend on this module only; they must not import
the registry or styling modules directly. That keeps the layer rendering
pipeline driven by reusable definitions: adding a new overlay means
registering a `LayerDefinition` and shipping a geojson file.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from huisChecker.layers.definitions import (
    LayerDefinition,
    LegendConfig,
    OpacityConfig,
    layer_registry,
)
from huisChecker.layers.styling import feature_color, feature_label


def _default_data_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def layers_dir(data_root: Path | None = None) -> Path:
    root = data_root if data_root is not None else _default_data_root()
    return root / "curated" / "layers"


def available_keys(data_root: Path | None = None) -> tuple[str, ...]:
    folder = layers_dir(data_root)
    return tuple(
        layer.key
        for layer in layer_registry.all()
        if (folder / layer.resolved_data_file).exists()
    )


def layer_metadata(key: str) -> dict[str, Any]:
    layer = layer_registry.get(key)
    return _metadata_dict(layer)


def registry_payload(keys: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    if keys is None:
        layers = layer_registry.all()
    else:
        layers = tuple(layer_registry.get(k) for k in keys)
    return [_metadata_dict(layer) for layer in layers]


def load_styled_geojson(key: str, data_root: Path | None = None) -> dict[str, Any] | None:
    layer = layer_registry.get(key)
    path = layers_dir(data_root) / layer.resolved_data_file
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    return enrich_geojson(layer, raw)


def enrich_geojson(layer: LayerDefinition, geojson: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `geojson` with `_color` and `_label` added per feature."""
    enriched = deepcopy(geojson)
    enriched.setdefault("type", "FeatureCollection")
    for feature in enriched.get("features", []):
        props = feature.setdefault("properties", {})
        color = feature_color(layer, props)
        if color is not None:
            props["_color"] = color
        label = feature_label(layer, props)
        if label is not None:
            props["_label"] = label
    return enriched


def _metadata_dict(layer: LayerDefinition) -> dict[str, Any]:
    return {
        "key": layer.key,
        "label": layer.label,
        "source_dataset_key": layer.source_dataset_key,
        "geometry_type": layer.geometry_type.value,
        "default_visible": layer.default_visible,
        "caveat": layer.caveat,
        "opacity": _opacity_dict(layer.opacity),
        "legend": _legend_dict(layer.legend),
    }


def _opacity_dict(opacity: OpacityConfig) -> dict[str, Any]:
    return {
        "default": opacity.default,
        "min": opacity.min,
        "max": opacity.max,
        "user_adjustable": opacity.user_adjustable,
    }


def _legend_dict(legend: LegendConfig | None) -> dict[str, Any] | None:
    if legend is None:
        return None
    return {
        "type": legend.type.value,
        "unit": legend.unit,
        "stops": [
            {"label": s.label, "color": s.color, "value": s.value}
            for s in legend.stops
        ],
    }


__all__ = [
    "available_keys",
    "enrich_geojson",
    "layer_metadata",
    "layers_dir",
    "load_styled_geojson",
    "registry_payload",
]
