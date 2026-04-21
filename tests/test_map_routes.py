"""Smoke tests for the /map endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from huisChecker.app.main import app

client = TestClient(app)


def test_layers_index_returns_all_registered() -> None:
    r = client.get("/map/layers.json")
    assert r.status_code == 200
    payload = r.json()
    keys = [layer["key"] for layer in payload["layers"]]
    assert "leefbaarometer_pc4" in keys
    assert "bag_footprints" in keys
    assert isinstance(payload["available"], list)


def test_layers_index_filtered_by_keys() -> None:
    r = client.get("/map/layers.json?keys=leefbaarometer_pc4,klimaateffect_flood")
    assert r.status_code == 200
    keys = [layer["key"] for layer in r.json()["layers"]]
    assert keys == ["leefbaarometer_pc4", "klimaateffect_flood"]


def test_layer_info_unknown_returns_404() -> None:
    r = client.get("/map/layers/no_such_layer.json")
    assert r.status_code == 404


def test_layer_geojson_serves_styled_features() -> None:
    r = client.get("/map/layers/leefbaarometer_pc4.geojson")
    assert r.status_code == 200
    payload = r.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["features"]
    first = payload["features"][0]["properties"]
    assert first["_color"].startswith("#")


def test_layer_geojson_unknown_returns_404() -> None:
    r = client.get("/map/layers/no_such_layer.geojson")
    assert r.status_code == 404


def test_explore_postcode_includes_map_partial() -> None:
    r = client.get("/explore/postcode/1011")
    assert r.status_code == 200
    body = r.text
    assert 'id="pc4-map"' in body
    expected = 'data-layer-keys="leefbaarometer_pc4,cbs_population_density_pc4,klimaateffect_flood"'
    assert expected in body


def test_address_preview_includes_focused_map() -> None:
    r = client.get("/address/1011AB-12")
    assert r.status_code == 200
    body = r.text
    assert 'id="preview-map"' in body
    assert "data-focus-lat" in body
