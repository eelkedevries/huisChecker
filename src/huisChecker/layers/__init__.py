"""Map layer configuration, styling and service."""

from huisChecker.layers.definitions import (
    GeometryType,
    LayerDefinition,
    LayerRegistry,
    LegendConfig,
    LegendStop,
    LegendType,
    OpacityConfig,
    layer_registry,
)
from huisChecker.layers.service import (
    available_keys,
    enrich_geojson,
    layer_metadata,
    load_styled_geojson,
    registry_payload,
)
from huisChecker.layers.styling import feature_color, feature_label, resolve_stop

__all__ = [
    "GeometryType",
    "LayerDefinition",
    "LayerRegistry",
    "LegendConfig",
    "LegendStop",
    "LegendType",
    "OpacityConfig",
    "available_keys",
    "enrich_geojson",
    "feature_color",
    "feature_label",
    "layer_metadata",
    "layer_registry",
    "load_styled_geojson",
    "registry_payload",
    "resolve_stop",
]
