"""Report module contracts.

A report module is a named section of the output. Its *contract* is
static configuration: which metrics and layers it uses, which source
datasets it depends on, and the caveat that is always shown with the
section. Runtime output is an instance of
`huisChecker.contracts.entities.ReportModuleResult`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field


class ReportModuleKey(StrEnum):
    BUILDING_BASICS = "building_basics"
    AREA_PROFILE = "area_profile"
    LIVEABILITY = "liveability"
    SAFETY_NUISANCE = "safety_nuisance"
    ENV_CLIMATE = "env_climate"
    CAVEATS_SOURCES = "caveats_sources"


class ReportModuleContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: ReportModuleKey
    label: str
    description: str
    metric_keys: tuple[str, ...] = ()
    layer_keys: tuple[str, ...] = ()
    source_dataset_keys: tuple[str, ...] = Field(default_factory=tuple)
    caveat: str
    required: bool = True  # if False, section is skipped when data is absent


class ReportModuleRegistry:
    def __init__(self) -> None:
        self._items: dict[ReportModuleKey, ReportModuleContract] = {}

    def register(self, contract: ReportModuleContract) -> ReportModuleContract:
        if contract.key in self._items:
            raise ValueError(f"module already registered: {contract.key}")
        self._items[contract.key] = contract
        return contract

    def get(self, key: ReportModuleKey | str) -> ReportModuleContract:
        k = ReportModuleKey(key)
        try:
            return self._items[k]
        except KeyError as exc:
            raise KeyError(f"unknown report module: {k}") from exc

    def all(self) -> tuple[ReportModuleContract, ...]:
        return tuple(self._items.values())

    def register_many(self, contracts: Iterable[ReportModuleContract]) -> None:
        for c in contracts:
            self.register(c)


report_module_registry = ReportModuleRegistry()


report_module_registry.register_many(
    [
        ReportModuleContract(
            key=ReportModuleKey.BUILDING_BASICS,
            label="Woning en gebouw",
            description="Basic building facts from BAG: construction year, surface, use.",
            metric_keys=("bag_construction_year",),
            layer_keys=("bag_footprints",),
            source_dataset_keys=("bag",),
            caveat="BAG data reflects registered facts; real-world state may differ.",
        ),
        ReportModuleContract(
            key=ReportModuleKey.AREA_PROFILE,
            label="Buurtprofiel",
            description="Population and demographics from CBS PC4.",
            metric_keys=("cbs_population_density",),
            layer_keys=("cbs_population_density_pc4",),
            source_dataset_keys=("cbs_kerncijfers_pc4",),
            caveat="PC4 averages; not address-level.",
        ),
        ReportModuleContract(
            key=ReportModuleKey.LIVEABILITY,
            label="Leefbaarheid",
            description="Source-native Leefbaarometer score for the PC4 area.",
            metric_keys=("leefbaarometer_score",),
            layer_keys=("leefbaarometer_pc4",),
            source_dataset_keys=("leefbaarometer",),
            caveat="Composite score published by Leefbaarometer; shown as-is.",
        ),
        ReportModuleContract(
            key=ReportModuleKey.SAFETY_NUISANCE,
            label="Veiligheid en overlast",
            description="Registered police incidents normalised per 1.000 inhabitants.",
            metric_keys=("politie_registered_incidents_per_1000",),
            layer_keys=(),
            source_dataset_keys=("politie_opendata", "cbs_kerncijfers_pc4"),
            caveat="Only reported incidents; under-reporting varies.",
        ),
        ReportModuleContract(
            key=ReportModuleKey.ENV_CLIMATE,
            label="Klimaat en leefomgeving",
            description="Climate risk indicators from Klimaateffectatlas.",
            metric_keys=("klimaateffect_flood_probability",),
            layer_keys=("klimaateffect_flood",),
            source_dataset_keys=("klimaateffectatlas", "atlas_leefomgeving"),
            caveat="Scenario-based modelling; classes, not precise probabilities.",
        ),
        ReportModuleContract(
            key=ReportModuleKey.CAVEATS_SOURCES,
            label="Bronnen en kanttekeningen",
            description="Consolidated list of sources, reference periods, and caveats.",
            metric_keys=(),
            layer_keys=(),
            source_dataset_keys=(),
            caveat="Always shown; no single source covers everything.",
            required=True,
        ),
    ]
)


__all__ = [
    "ReportModuleContract",
    "ReportModuleKey",
    "ReportModuleRegistry",
    "report_module_registry",
]
