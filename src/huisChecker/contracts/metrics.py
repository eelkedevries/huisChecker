"""Metric-definition system.

A metric is any comparable number we publish in a report or map. Every
metric has a single definition object: where it comes from, which
geography it applies to, its units, a mandatory caveat string, and
the preferred way to contextualise it (source-native score, municipal
average, etc.). Report modules and map layers reference metrics by key
only; adding a new measure means adding a definition + ETL, never a
code branch.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field


class GeographyLevel(StrEnum):
    ADDRESS = "address"
    BAG_OBJECT = "bag_object"
    POSTCODE4 = "postcode4"
    MUNICIPALITY = "municipality"
    PROVINCE = "province"
    NATIONAL = "national"


class ComparisonMode(StrEnum):
    """How a metric should be contextualised when shown to a user."""

    NONE = "none"
    SOURCE_NATIVE = "source_native"  # e.g. Leefbaarometer score; show raw band
    MUNICIPAL_AVERAGE = "municipal_average"
    PROVINCIAL_AVERAGE = "provincial_average"
    NATIONAL_AVERAGE = "national_average"
    HISTORICAL = "historical"  # same geography, earlier period


class MetricDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    geography_level: GeographyLevel
    source_dataset_key: str
    unit: str | None  # None when the metric is an index/score with no unit
    caveat: str  # required; rendered next to the value
    preferred_comparison: ComparisonMode


class MetricRegistry:
    """In-memory, append-only registry of metric definitions."""

    def __init__(self) -> None:
        self._items: dict[str, MetricDefinition] = {}

    def register(self, definition: MetricDefinition) -> MetricDefinition:
        if definition.key in self._items:
            raise ValueError(f"metric already registered: {definition.key}")
        self._items[definition.key] = definition
        return definition

    def get(self, key: str) -> MetricDefinition:
        try:
            return self._items[key]
        except KeyError as exc:
            raise KeyError(f"unknown metric: {key}") from exc

    def all(self) -> tuple[MetricDefinition, ...]:
        return tuple(self._items.values())

    def by_source(self, source_dataset_key: str) -> tuple[MetricDefinition, ...]:
        return tuple(m for m in self._items.values() if m.source_dataset_key == source_dataset_key)

    def register_many(self, definitions: Iterable[MetricDefinition]) -> None:
        for d in definitions:
            self.register(d)


metric_registry = MetricRegistry()


# --- seed metrics -----------------------------------------------------------
# Kept intentionally small: one or two per data-source group, enough to
# exercise the registry and give later prompts concrete references.

metric_registry.register_many(
    [
        MetricDefinition(
            key="leefbaarometer_score",
            label="Leefbaarometer-score",
            geography_level=GeographyLevel.POSTCODE4,
            source_dataset_key="leefbaarometer",
            unit=None,
            caveat=(
                "Source-native composite score. Shown as published by "
                "Leefbaarometer; do not recombine with other indicators."
            ),
            preferred_comparison=ComparisonMode.SOURCE_NATIVE,
        ),
        MetricDefinition(
            key="cbs_population_density",
            label="Bevolkingsdichtheid",
            geography_level=GeographyLevel.POSTCODE4,
            source_dataset_key="cbs_kerncijfers_pc4",
            unit="inhabitants/km2",
            caveat="CBS PC4 snapshot; value is an area average, not address-level.",
            preferred_comparison=ComparisonMode.MUNICIPAL_AVERAGE,
        ),
        MetricDefinition(
            key="bag_construction_year",
            label="Bouwjaar",
            geography_level=GeographyLevel.BAG_OBJECT,
            source_dataset_key="bag",
            unit="year",
            caveat="BAG registered construction year; renovations not reflected.",
            preferred_comparison=ComparisonMode.NONE,
        ),
        MetricDefinition(
            key="politie_registered_incidents_per_1000",
            label="Geregistreerde incidenten per 1.000 inwoners",
            geography_level=GeographyLevel.POSTCODE4,
            source_dataset_key="politie_opendata",
            unit="incidents/1000",
            caveat=(
                "Only incidents reported to the police; under-reporting varies by "
                "incident type and area."
            ),
            preferred_comparison=ComparisonMode.NATIONAL_AVERAGE,
        ),
        MetricDefinition(
            key="klimaateffect_flood_probability",
            label="Overstromingskans",
            geography_level=GeographyLevel.ADDRESS,
            source_dataset_key="klimaateffectatlas",
            unit="probability_class",
            caveat=(
                "Scenario-based modelling; classes, not precise probabilities. "
                "Does not account for building-level flood defences."
            ),
            preferred_comparison=ComparisonMode.SOURCE_NATIVE,
        ),
    ]
)


__all__ = [
    "ComparisonMode",
    "GeographyLevel",
    "MetricDefinition",
    "MetricRegistry",
    "metric_registry",
]
