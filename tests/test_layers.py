"""Tests for the layer registry, styling, and service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from huisChecker.layers import (
    GeometryType,
    LayerDefinition,
    LayerRegistry,
    LegendConfig,
    LegendStop,
    LegendType,
    OpacityConfig,
    enrich_geojson,
    feature_color,
    feature_label,
    layer_registry,
    load_styled_geojson,
    registry_payload,
)
from huisChecker.layers.service import available_keys


def test_layer_registry_default_visible_subset() -> None:
    defaults = layer_registry.default_visible()
    keys = {d.key for d in defaults}
    assert "leefbaarometer_pc4" in keys


def test_layer_registry_blocks_duplicate() -> None:
    reg = LayerRegistry()
    d = LayerDefinition(
        key="t_layer",
        label="t",
        source_dataset_key="src",
        geometry_type=GeometryType.POLYGON,
        supported_geographies=(),
        value_field=None,
        legend=None,
        caveat="c",
    )
    reg.register(d)
    with pytest.raises(ValueError):
        reg.register(d)


def test_legend_stop_requires_hex_color() -> None:
    with pytest.raises(Exception):
        LegendConfig(
            type=LegendType.CATEGORICAL,
            stops=(LegendStop(label="x", color="red"),),
        )


def test_opacity_config_bounds() -> None:
    with pytest.raises(Exception):
        OpacityConfig(default=1.5, min=0.0, max=1.0)


def test_feature_color_categorical_match() -> None:
    layer = layer_registry.get("leefbaarometer_pc4")
    assert feature_color(layer, {"band": "voldoende"}) == "#a6d96a"
    assert feature_label(layer, {"band": "voldoende"}) == "voldoende"


def test_feature_color_categorical_unknown_value() -> None:
    layer = layer_registry.get("leefbaarometer_pc4")
    assert feature_color(layer, {"band": "onbekend"}) is None


def test_feature_color_quantile_bins_by_range() -> None:
    layer = layer_registry.get("cbs_population_density_pc4")
    # legend has 5 stops across min=1000, max=8000 -> bin width 1400
    low_stop = layer.legend.stops[0]
    high_stop = layer.legend.stops[-1]
    assert feature_color(layer, {"population_density": 500}) == low_stop.color
    assert feature_color(layer, {"population_density": 9000}) == high_stop.color
    # 6500 -> idx = int((6500 - 1000) / 7000 * 5) = int(3.928) = 3
    mid = feature_color(layer, {"population_density": 6500})
    assert mid == layer.legend.stops[3].color


def test_feature_color_missing_property() -> None:
    layer = layer_registry.get("leefbaarometer_pc4")
    assert feature_color(layer, {}) is None


def test_reference_layer_has_no_color() -> None:
    layer = layer_registry.get("bag_footprints")
    assert feature_color(layer, {"bag_object_id": "x"}) is None


def test_enrich_geojson_adds_color_and_label() -> None:
    layer = layer_registry.get("leefbaarometer_pc4")
    raw = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"band": "goed"},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }
        ],
    }
    enriched = enrich_geojson(layer, raw)
    props = enriched["features"][0]["properties"]
    assert props["_color"] == "#1a9850"
    assert props["_label"] == "goed"


def test_enrich_geojson_skips_missing_value() -> None:
    layer = layer_registry.get("leefbaarometer_pc4")
    raw = {"type": "FeatureCollection", "features": [{"properties": {}}]}
    enriched = enrich_geojson(layer, raw)
    assert "_color" not in enriched["features"][0]["properties"]


def test_registry_payload_shapes() -> None:
    payload = registry_payload(("leefbaarometer_pc4", "klimaateffect_flood"))
    assert [p["key"] for p in payload] == ["leefbaarometer_pc4", "klimaateffect_flood"]
    lb = payload[0]
    assert lb["legend"]["type"] == "categorical"
    assert lb["opacity"]["default"] == 0.7
    assert lb["caveat"]


def test_registry_payload_rejects_unknown_key() -> None:
    with pytest.raises(KeyError):
        registry_payload(("no_such_layer",))


def test_load_styled_geojson_from_repo_data() -> None:
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    assert data["type"] == "FeatureCollection"
    assert data["features"], "expected at least one feature"
    props = data["features"][0]["properties"]
    assert "_color" in props and props["_color"].startswith("#")


def test_load_styled_geojson_missing_data_file(tmp_path: Path) -> None:
    # Layer is registered but no geojson in this tmp root.
    assert load_styled_geojson("leefbaarometer_pc4", data_root=tmp_path) is None


def test_available_keys_matches_repo(tmp_path: Path) -> None:
    # Copy one layer into tmp and check only that one is reported.
    layers_dir = tmp_path / "curated" / "layers"
    layers_dir.mkdir(parents=True)
    (layers_dir / "leefbaarometer_pc4.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": []})
    )
    keys = available_keys(data_root=tmp_path)
    assert keys == ("leefbaarometer_pc4",)


def test_every_registered_layer_with_data_file_round_trips() -> None:
    """Catch config drift: any shipped geojson must load + enrich cleanly."""
    for key in available_keys():
        data = load_styled_geojson(key)
        assert data is not None, key
        assert data.get("type") == "FeatureCollection", key
        layer = layer_registry.get(key)
        if layer.legend is None:
            continue
        # At least one feature should successfully resolve a color.
        has_color = any(
            "_color" in (f.get("properties") or {}) for f in data["features"]
        )
        assert has_color, f"{key}: no features resolved a legend color"
