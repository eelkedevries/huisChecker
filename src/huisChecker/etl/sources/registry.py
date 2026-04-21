"""Registry of `SourceDataset` entries for the MVP source groups.

Deferred / out-of-scope sources must not be added here without a
corresponding entry in `docs-shared/decisions.md`.
"""

from __future__ import annotations

from huisChecker.contracts import SourceDataset

CORE_SOURCES: tuple[SourceDataset, ...] = (
    SourceDataset(
        key="cbs_kerncijfers_pc4",
        label="CBS kerncijfers per postcode 4",
        provider="CBS",
        url="https://www.cbs.nl/nl-nl/maatwerk/2024/kerncijfers-per-postcode",
        refresh_cadence="annual",
        coverage="NL, postcode4 + gemeente + provincie",
        licence="CBS-open-data",
        notes=(
            "Annual snapshot. PC4 averages, not address-level. "
            "Includes municipality and province rollups."
        ),
    ),
    SourceDataset(
        key="bag",
        label="BAG / PDOK address and building registry",
        provider="Kadaster / PDOK",
        url="https://www.pdok.nl/introductie/-/article/basisregistratie-adressen-en-gebouwen-ba-1",
        refresh_cadence="ad hoc",
        coverage="NL, nummeraanduiding + verblijfsobject",
        licence="CC0 (BAG)",
        notes=(
            "Use PDOK Locatieserver for address lookup; BAG extract for building facts. "
            "Refresh is ad hoc: take a recent PDOK snapshot, do not chase daily deltas in MVP."
        ),
    ),
    SourceDataset(
        key="leefbaarometer",
        label="Leefbaarometer 3.0 scores and dimensions",
        provider="Ministerie van BZK",
        url="https://www.leefbaarometer.nl/",
        refresh_cadence="biennial",
        coverage="NL, postcode4 + buurt",
        licence="Open data (CC-BY)",
        notes=(
            "Composite score is source-native. Do not re-aggregate into a huisChecker score. "
            "Reference period drives MVP display."
        ),
    ),
    SourceDataset(
        key="politie_opendata",
        label="Politie open data: crime and nuisance",
        provider="Nationale Politie",
        url="https://data.politie.nl/",
        refresh_cadence="monthly",
        coverage="NL, per municipality and per district/wijk",
        licence="CC-BY",
        notes=(
            "Registered incidents only; strong under-reporting for several categories. "
            "Normalised per 1000 inhabitants using CBS population."
        ),
    ),
    SourceDataset(
        key="klimaateffectatlas",
        label="Klimaateffectatlas selected climate risk layers",
        provider="Stichting CAS / Rijk",
        url="https://www.klimaateffectatlas.nl/",
        refresh_cadence="ad hoc",
        coverage="NL, raster-backed layers",
        licence="Open data",
        notes=(
            "MVP pulls only stable, downloadable layers (flood probability class, heat). "
            "No runtime dependency on the portal."
        ),
    ),
    SourceDataset(
        key="atlas_leefomgeving",
        label="Atlas Leefomgeving selected layers",
        provider="RIVM / partners",
        url="https://www.atlasleefomgeving.nl/",
        refresh_cadence="ad hoc",
        coverage="NL, varies per layer",
        licence="Open data (layer-specific)",
        notes=(
            "Only layers with stable downloadable/service-backed sources are ingested. "
            "Portal is not a runtime dependency."
        ),
    ),
)


class _SourceRegistry:
    def __init__(self, items: tuple[SourceDataset, ...]) -> None:
        self._items: dict[str, SourceDataset] = {s.key: s for s in items}

    def get(self, key: str) -> SourceDataset:
        try:
            return self._items[key]
        except KeyError as exc:
            raise KeyError(f"unknown source dataset: {key}") from exc

    def all(self) -> tuple[SourceDataset, ...]:
        return tuple(self._items.values())

    def keys(self) -> tuple[str, ...]:
        return tuple(self._items.keys())


source_registry = _SourceRegistry(CORE_SOURCES)


__all__ = ["CORE_SOURCES", "source_registry"]
