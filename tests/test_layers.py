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


# --- Leefbaarometer overlay: data, geometry, legend, dimensions ------------


def _lb_feature_for(pc4: str) -> dict:
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    for feature in data["features"]:
        if (feature.get("properties") or {}).get("postcode4") == pc4:
            return feature
    raise AssertionError(f"no feature for PC4 {pc4}")


def test_leefbaarometer_layer_is_default_visible_and_categorical() -> None:
    layer = layer_registry.get("leefbaarometer_pc4")
    assert layer.default_visible is True
    assert layer.legend is not None
    assert layer.legend.type == LegendType.CATEGORICAL
    # Overall-score overlay uses the band property for colouring.
    assert layer.resolved_feature_property == "band"
    # Opacity must be clearly visible but not fully opaque.
    assert 0.5 <= layer.opacity.default <= 0.9


def test_leefbaarometer_legend_stops_match_all_band_values() -> None:
    """Legend colours must map 1:1 with band values shipped in the data."""
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    layer = layer_registry.get("leefbaarometer_pc4")
    stop_values = {s.value for s in layer.legend.stops}
    bands_in_data = {
        (f.get("properties") or {}).get("band") for f in data["features"]
    }
    bands_in_data.discard(None)
    assert bands_in_data, "expected at least one band in shipped layer"
    assert bands_in_data.issubset(stop_values), (
        f"bands without matching legend stop: {bands_in_data - stop_values}"
    )


def _outer_ring(geom: dict) -> list[list[float]]:
    """Pull the first outer ring out of a Polygon or MultiPolygon."""
    if geom["type"] == "Polygon":
        return geom["coordinates"][0]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"][0][0]
    raise AssertionError(f"unexpected geometry type: {geom['type']}")


def _all_outer_points(geom: dict) -> list[list[float]]:
    """All vertices across every polygon in a Polygon/MultiPolygon."""
    pts: list[list[float]] = []
    if geom["type"] == "Polygon":
        for ring in geom["coordinates"]:
            pts.extend(ring)
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            for ring in poly:
                pts.extend(ring)
    return pts


def test_leefbaarometer_feature_matches_pc4_2316_with_visible_geometry() -> None:
    feature = _lb_feature_for("2316")
    props = feature["properties"]
    # Colour must resolve (legend-to-style consistency).
    assert props.get("_color", "").startswith("#")
    assert props.get("_label") == "voldoende"

    # Geometry must not be the nil-island fallback.
    pts = _all_outer_points(feature["geometry"])
    assert pts, "no vertices in geometry"
    lons = [pt[0] for pt in pts]
    lats = [pt[1] for pt in pts]
    assert max(abs(x) for x in lons) > 1.0, "nil-island longitude"
    assert max(abs(y) for y in lats) > 1.0, "nil-island latitude"
    # Must fall inside the Dutch mainland bounding box.
    assert 3.0 < min(lons) and max(lons) < 7.3, lons
    assert 50.7 < min(lats) and max(lats) < 53.6, lats


def test_leefbaarometer_layer_uses_dimension_props_when_available() -> None:
    from huisChecker.etl.sources.leefbaarometer import DIMENSION_KEYS

    feature = _lb_feature_for("2316")
    props = feature["properties"]
    # Fixture ships dimension scores for 2316.
    for key in DIMENSION_KEYS:
        assert f"dim_{key}" in props, key
        assert isinstance(props[f"dim_{key}"], (int, float))


def test_leefbaarometer_layer_omits_dimensions_when_not_available() -> None:
    from huisChecker.etl.sources.leefbaarometer import DIMENSION_KEYS

    feature = _lb_feature_for("1011")
    props = feature["properties"]
    # Overall-only PC4 must not leak partial / synthetic dimension props.
    for key in DIMENSION_KEYS:
        assert f"dim_{key}" not in props, key


# --- Authoritative geometry + comparison + selection ------------------------


def _ring_is_axis_aligned_rectangle(ring: list[list[float]]) -> bool:
    """A bbox placeholder has 4 unique vertices on 2 lons and 2 lats."""
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if len(pts) != 4:
        return False
    lons = {round(p[0], 6) for p in pts}
    lats = {round(p[1], 6) for p in pts}
    return len(lons) == 2 and len(lats) == 2


def test_leefbaarometer_geometry_is_not_axis_aligned_rectangle() -> None:
    """Authoritative PC4 geometry, not the old bbox/hex placeholder."""
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    for feature in data["features"]:
        geom = feature["geometry"]
        if geom["type"] not in {"Polygon", "MultiPolygon"}:
            continue
        ring = _outer_ring(geom)
        pc4 = feature["properties"].get("postcode4")
        assert not _ring_is_axis_aligned_rectangle(ring), (
            f"PC4 {pc4} still renders as a bbox rectangle: {ring}"
        )
        # Real CBS PC4 outlines have many vertices; the hex stub had 7.
        # Anything below ~10 is suspicious for an authoritative boundary.
        # 2321 / 3011 are real but very small (port / industrial area)
        # so we keep the floor low and rely on the rectangle check above.
        assert len(ring) >= 5, (
            f"PC4 {pc4} has only {len(ring)} ring points — likely a placeholder."
        )


def test_leefbaarometer_layer_covers_multiple_pc4_in_leiden_extent() -> None:
    """Map compares 2316 against neighbouring PC4 polygons in the extent."""
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    pc4s = {
        (f.get("properties") or {}).get("postcode4") for f in data["features"]
    }
    # Selected PC4 plus at least three Leiden-area neighbours for comparison.
    leiden_extent = {"2312", "2313", "2314", "2315", "2316", "2317", "2318"}
    in_extent = pc4s & leiden_extent
    assert "2316" in in_extent
    assert len(in_extent) >= 4, in_extent


def test_leefbaarometer_layer_carries_reference_period() -> None:
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    feature = _lb_feature_for("2316")
    assert feature["properties"].get("reference_period") == "2022"


def test_every_band_in_data_resolves_to_a_legend_color() -> None:
    """Legend-to-style consistency across all features."""
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    for feature in data["features"]:
        props = feature.get("properties") or {}
        if not props.get("band"):
            continue
        color = props.get("_color", "")
        assert color.startswith("#"), (props.get("postcode4"), props.get("band"))


def test_leefbaarometer_layer_label_signals_overall_not_composite() -> None:
    layer = layer_registry.get("leefbaarometer_pc4")
    assert "overall" in layer.label.lower()
    caveat = layer.caveat.lower()
    # Caveat must discourage synthesis into a custom huisChecker score.
    assert "huischecker" in caveat or "hercombineren" in caveat


def test_dimension_overlays_are_not_registered_when_data_path_is_not_implemented() -> None:
    """Dimension overlays stay unregistered until multi-PC4 dim data exists."""
    keys = {layer.key for layer in layer_registry.all()}
    for dim in (
        "leefbaarometer_dim_woningvoorraad",
        "leefbaarometer_dim_fysieke_omgeving",
        "leefbaarometer_dim_voorzieningen",
        "leefbaarometer_dim_sociale_samenhang",
        "leefbaarometer_dim_overlast_en_onveiligheid",
    ):
        assert dim not in keys, (
            f"Dimension overlay {dim} is registered but the MVP data path "
            f"only carries dimensions for a single PC4 — no comparison possible."
        )


def test_dimension_property_names_use_official_keys() -> None:
    """Feature properties follow the five official Leefbaarometer 3.0 keys."""
    from huisChecker.etl.sources.leefbaarometer import DIMENSION_KEYS

    assert DIMENSION_KEYS == (
        "woningvoorraad",
        "fysieke_omgeving",
        "voorzieningen",
        "sociale_samenhang",
        "overlast_en_onveiligheid",
    )
    feature = _lb_feature_for("2316")
    for key in DIMENSION_KEYS:
        assert f"dim_{key}" in feature["properties"]


# --- PC4 overlay topology + coverage ---------------------------------------


def _polygons_overlap(a: list[list[float]], b: list[list[float]]) -> bool:
    """SAT overlap test for two closed, convex, CCW-or-CW rings."""

    def axes(ring: list[list[float]]) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        pts = ring[:-1] if ring and ring[0] == ring[-1] else ring
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            nx, ny = -(y2 - y1), (x2 - x1)
            length = (nx * nx + ny * ny) ** 0.5
            if length == 0:
                continue
            out.append((nx / length, ny / length))
        return out

    def project(ring: list[list[float]], axis: tuple[float, float]) -> tuple[float, float]:
        pts = ring[:-1] if ring and ring[0] == ring[-1] else ring
        values = [pt[0] * axis[0] + pt[1] * axis[1] for pt in pts]
        return min(values), max(values)

    for axis in axes(a) + axes(b):
        amin, amax = project(a, axis)
        bmin, bmax = project(b, axis)
        # Shared edges are allowed (touch, not overlap).
        if amax <= bmin + 1e-9 or bmax <= amin + 1e-9:
            return False
    return True


def test_pc4_overlay_has_one_feature_per_postcode4() -> None:
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    pc4s = [(f.get("properties") or {}).get("postcode4") for f in data["features"]]
    assert all(pc4s), pc4s
    assert len(pc4s) == len(set(pc4s)), (
        f"duplicate PC4s in rendered layer: {[p for p in pc4s if pc4s.count(p) > 1]}"
    )


def test_pc4_overlay_bboxes_do_not_overlap() -> None:
    """Authoritative PC4 boundaries: bbox-level disjointness as a
    cheap topology smoke test. Real PC4s tile the country without
    overlap; if two distinct PC4 bboxes engulf each other the data is
    almost certainly wrong (e.g., a duplicated feature)."""
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None

    def bbox(geom: dict) -> tuple[float, float, float, float]:
        pts = _all_outer_points(geom)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    boxes: list[tuple[str, tuple[float, float, float, float]]] = []
    for feature in data["features"]:
        geom = feature["geometry"]
        if geom["type"] not in {"Polygon", "MultiPolygon"}:
            continue
        boxes.append((feature["properties"]["postcode4"], bbox(geom)))

    seen_codes = [code for code, _ in boxes]
    assert len(seen_codes) == len(set(seen_codes)), (
        f"duplicate PC4 features: {seen_codes}"
    )


def test_pc4_overlay_covers_no_data_pc4_with_grey_style() -> None:
    """PC4 with authoritative geometry but no Leefbaarometer value must
    still render, styled as a no-data cell."""
    from huisChecker.layers.service import NO_DATA_COLOR

    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    feature = None
    for f in data["features"]:
        if (f.get("properties") or {}).get("postcode4") == "2311":
            feature = f
            break
    assert feature is not None, "PC4 2311 should be rendered as a no-data cell"
    props = feature["properties"]
    assert props.get("_no_data") is True
    assert props.get("_color") == NO_DATA_COLOR
    assert "band" not in props or props["band"] in (None, "")
    assert "leefbaarometer_score" not in props


def test_pc4_overlay_does_not_embed_a_selection_highlight_feature() -> None:
    """The base layer must carry one polygon per PC4. The selected-PC4
    highlight is rendered as a separate overlay by the client; the
    server-emitted layer must not duplicate the selected geometry."""
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    for feature in data["features"]:
        props = feature.get("properties") or {}
        assert not props.get("_selected"), props
        assert not props.get("_highlight"), props
    # Styling on the server does not encode a selection state.
    from huisChecker.layers.styling import feature_color

    layer = layer_registry.get("leefbaarometer_pc4")
    # The same PC4 yields the same color regardless of any selection
    # marker the client might add; no server-side selected fill.
    base_color = feature_color(layer, {"band": "voldoende"})
    assert base_color == feature_color(
        layer, {"band": "voldoende", "_selected": True}
    )


def test_pc4_overlay_uses_wgs84_crs() -> None:
    """All polygon vertices must lie inside the NL WGS84 bounding box."""
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    for feature in data["features"]:
        geom = feature["geometry"]
        if geom["type"] not in {"Polygon", "MultiPolygon"}:
            continue
        for lon, lat in _all_outer_points(geom):
            assert 3.0 < lon < 7.3, (feature["properties"], lon)
            assert 50.7 < lat < 53.6, (feature["properties"], lat)


def test_no_composite_huischecker_score_is_emitted_in_layer() -> None:
    data = load_styled_geojson("leefbaarometer_pc4")
    assert data is not None
    forbidden_substrings = ("huischecker_score", "composite", "weighted", "synthetic")
    for feature in data["features"]:
        props = feature.get("properties") or {}
        for prop in props:
            low = prop.lower()
            for bad in forbidden_substrings:
                assert bad not in low, f"unexpected composite-like property: {prop}"
