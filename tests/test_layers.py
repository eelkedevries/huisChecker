import pytest

from huisChecker.layers import (
    GeometryType,
    LayerDefinition,
    LayerRegistry,
    LegendConfig,
    LegendStop,
    LegendType,
    OpacityConfig,
    layer_registry,
)


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
