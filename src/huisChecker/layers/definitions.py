"""Map layer-definition system.

A layer is a map overlay tied to a single source dataset and a single
value field. Report modules and the area-explore UI reference layers
by key only, so adding a new overlay means adding a definition and
ETL, not a code branch.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from huisChecker.contracts.metrics import GeographyLevel


class GeometryType(StrEnum):
    POINT = "point"
    LINESTRING = "linestring"
    POLYGON = "polygon"
    RASTER = "raster"


class LegendType(StrEnum):
    CATEGORICAL = "categorical"
    QUANTILE = "quantile"
    CONTINUOUS = "continuous"


class LegendStop(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    value: float | str | None = None


class LegendConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: LegendType
    stops: tuple[LegendStop, ...]
    min: float | None = None
    max: float | None = None
    unit: str | None = None


class OpacityConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default: float = Field(ge=0.0, le=1.0)
    min: float = Field(ge=0.0, le=1.0)
    max: float = Field(ge=0.0, le=1.0)
    user_adjustable: bool = True


class RemoteTileConfig(BaseModel):
    """Pointer to a remote WMS/WMTS service that renders this overlay.

    When set, the layer is painted client-side from the remote service
    rather than from a local geojson file. `layer_name` is the WMS
    `LAYERS` param; `attribution` shows up in the Leaflet corner.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = Field(default="wms", pattern=r"^(wms|wmts|xyz)$")
    tile_url: str
    layer_name: str | None = None
    attribution: str = ""
    format: str = "image/png"
    transparent: bool = True
    explanatory_note: str | None = None


class LayerDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    source_dataset_key: str
    geometry_type: GeometryType
    supported_geographies: tuple[GeographyLevel, ...]
    value_field: str | None  # None for reference layers (e.g. BAG footprint)
    legend: LegendConfig | None
    default_visible: bool = False
    opacity: OpacityConfig = OpacityConfig(default=0.7, min=0.1, max=1.0)
    caveat: str
    # Feature property key in the geojson used to resolve legend color for
    # categorical layers; defaults to `value_field`. Quantile/continuous
    # layers always read the numeric `value_field`.
    feature_property: str | None = None
    # Filename of curated geojson under data/curated/layers/. Defaults to
    # f"{key}.geojson" if not set.
    data_file: str | None = None
    # Remote tile service pointer for remote-first overlays. When set, the
    # frontend renders this layer from the service; `data_file` is optional.
    remote: RemoteTileConfig | None = None

    @property
    def resolved_feature_property(self) -> str | None:
        return self.feature_property or self.value_field

    @property
    def resolved_data_file(self) -> str:
        return self.data_file or f"{self.key}.geojson"


class LayerRegistry:
    def __init__(self) -> None:
        self._items: dict[str, LayerDefinition] = {}

    def register(self, definition: LayerDefinition) -> LayerDefinition:
        if definition.key in self._items:
            raise ValueError(f"layer already registered: {definition.key}")
        self._items[definition.key] = definition
        return definition

    def get(self, key: str) -> LayerDefinition:
        try:
            return self._items[key]
        except KeyError as exc:
            raise KeyError(f"unknown layer: {key}") from exc

    def has(self, key: str) -> bool:
        return key in self._items

    def all(self) -> tuple[LayerDefinition, ...]:
        return tuple(self._items.values())

    def default_visible(self) -> tuple[LayerDefinition, ...]:
        return tuple(d for d in self._items.values() if d.default_visible)

    def register_many(self, definitions: Iterable[LayerDefinition]) -> None:
        for d in definitions:
            self.register(d)


layer_registry = LayerRegistry()


# --- seed layers ------------------------------------------------------------

layer_registry.register_many(
    [
        LayerDefinition(
            key="leefbaarometer_pc4",
            label="Leefbaarometer (PC4)",
            source_dataset_key="leefbaarometer",
            geometry_type=GeometryType.POLYGON,
            supported_geographies=(GeographyLevel.POSTCODE4,),
            value_field="leefbaarometer_score",
            feature_property="band",
            legend=LegendConfig(
                type=LegendType.CATEGORICAL,
                stops=(
                    LegendStop(label="zeer onvoldoende", color="#7f0000", value="zeer_onvoldoende"),
                    LegendStop(label="onvoldoende", color="#d7301f", value="onvoldoende"),
                    LegendStop(label="matig", color="#fdae61", value="matig"),
                    LegendStop(label="voldoende", color="#a6d96a", value="voldoende"),
                    LegendStop(label="goed", color="#1a9850", value="goed"),
                    LegendStop(label="zeer goed", color="#006837", value="zeer_goed"),
                ),
            ),
            default_visible=True,
            caveat="Source-native bands; do not reinterpret numerically.",
        ),
        LayerDefinition(
            key="cbs_population_density_pc4",
            label="Bevolkingsdichtheid (PC4)",
            source_dataset_key="cbs_kerncijfers_pc4",
            geometry_type=GeometryType.POLYGON,
            supported_geographies=(GeographyLevel.POSTCODE4,),
            value_field="cbs_population_density",
            feature_property="population_density",
            legend=LegendConfig(
                type=LegendType.QUANTILE,
                stops=(
                    LegendStop(label="laag", color="#f7fcf5"),
                    LegendStop(label="onder gemiddelde", color="#c7e9c0"),
                    LegendStop(label="gemiddeld", color="#74c476"),
                    LegendStop(label="boven gemiddelde", color="#238b45"),
                    LegendStop(label="hoog", color="#00441b"),
                ),
                min=1000.0,
                max=8000.0,
                unit="inwoners/km²",
            ),
            caveat="CBS PC4 snapshot; values are area averages.",
        ),
        LayerDefinition(
            key="klimaateffect_flood",
            label="Overstromingskans",
            source_dataset_key="klimaateffectatlas",
            geometry_type=GeometryType.POLYGON,
            supported_geographies=(GeographyLevel.ADDRESS, GeographyLevel.POSTCODE4),
            value_field="klimaateffect_flood_probability",
            feature_property="class",
            legend=LegendConfig(
                type=LegendType.CATEGORICAL,
                stops=(
                    LegendStop(label="zeer klein", color="#edf8fb", value="zeer_klein"),
                    LegendStop(label="klein", color="#b3cde3", value="klein"),
                    LegendStop(label="middelgroot", color="#8c96c6", value="middelgroot"),
                    LegendStop(label="groot", color="#8856a7", value="groot"),
                    LegendStop(label="zeer groot", color="#810f7c", value="zeer_groot"),
                ),
            ),
            opacity=OpacityConfig(default=0.5, min=0.1, max=0.9),
            caveat="Scenario-based model; classes, not precise probabilities.",
        ),
        LayerDefinition(
            key="bag_footprints",
            label="BAG pandcontouren",
            source_dataset_key="bag",
            geometry_type=GeometryType.POINT,
            supported_geographies=(GeographyLevel.ADDRESS, GeographyLevel.BAG_OBJECT),
            value_field=None,
            legend=None,
            caveat="Reference layer only; no value encoded.",
        ),
        LayerDefinition(
            key="klimaateffect_flood_wms",
            label="Overstromingskans (KEA WMS)",
            source_dataset_key="klimaateffectatlas",
            geometry_type=GeometryType.RASTER,
            supported_geographies=(GeographyLevel.POSTCODE4,),
            value_field=None,
            legend=None,
            caveat="Rendered live from Klimaateffectatlas WMS; scenario-based classes.",
            remote=RemoteTileConfig(
                kind="wms",
                tile_url="https://service.pdok.nl/rws/klimaateffectatlas/wms/v1_0",
                layer_name="overstromingskans_2050",
                attribution="Klimaateffectatlas (CAS)",
                explanatory_note=(
                    "Laag wordt rechtstreeks van de Klimaateffectatlas WMS "
                    "gehaald; bij storing of geen dekking toont de kaart een lege "
                    "overlay met deze toelichting."
                ),
            ),
        ),
    ]
)


__all__ = [
    "GeometryType",
    "LayerDefinition",
    "LayerRegistry",
    "LegendConfig",
    "LegendStop",
    "LegendType",
    "OpacityConfig",
    "RemoteTileConfig",
    "layer_registry",
]
