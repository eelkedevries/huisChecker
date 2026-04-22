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
        refresh_cadence="jaarlijks",
        coverage="NL, postcode4 + gemeente + provincie",
        licence="CBS-open-data",
        notes=(
            "Jaarlijkse snapshot. Gemiddelden per PC4-gebied, niet adresspecifiek. "
            "Bevat rollups op gemeente- en provinciaal niveau."
        ),
    ),
    SourceDataset(
        key="bag",
        label="BAG / PDOK adres- en gebouwenregistratie",
        provider="Kadaster / PDOK",
        url="https://www.pdok.nl/introductie/-/article/basisregistratie-adressen-en-gebouwen-ba-1",
        refresh_cadence="ad hoc",
        coverage="NL, nummeraanduiding + verblijfsobject",
        licence="CC0 (BAG)",
        notes=(
            "Adresvalidatie via PDOK Locatieserver; gebouwkenmerken via BAG-extract. "
            "Peildatum op basis van meest recente PDOK-snapshot."
        ),
    ),
    SourceDataset(
        key="leefbaarometer",
        label="Leefbaarometer 3.0 scores en dimensies",
        provider="Ministerie van BZK",
        url="https://www.leefbaarometer.nl/",
        refresh_cadence="tweejaarlijks",
        coverage="NL, postcode4 + buurt",
        licence="Open data (CC-BY)",
        notes=(
            "Samengestelde bron-eigen score; niet hercombineren tot een huisChecker-score. "
            "Peiljaar bepaalt welke editie wordt getoond."
        ),
    ),
    SourceDataset(
        key="politie_opendata",
        label="Politie open data: misdaad en overlast",
        provider="Nationale Politie",
        url="https://data.politie.nl/",
        refresh_cadence="maandelijks",
        coverage="NL, per gemeente en wijk",
        licence="CC-BY",
        notes=(
            "Alleen geregistreerde meldingen. "
            "Genormaliseerd per 1.000 inwoners op basis van CBS-bevolkingsdata."
        ),
    ),
    SourceDataset(
        key="klimaateffectatlas",
        label="Klimaateffectatlas geselecteerde klimaatrisico-lagen",
        provider="Stichting CAS / Rijk",
        url="https://www.klimaateffectatlas.nl/",
        refresh_cadence="ad hoc",
        coverage="NL, rasterlagen",
        licence="Open data",
        notes=(
            "Alleen stabiele, downloadbare lagen (overstromingskansklasse, hitte). "
            "Geen runtime-afhankelijkheid van het portaal."
        ),
    ),
    SourceDataset(
        key="atlas_leefomgeving",
        label="Atlas Leefomgeving geselecteerde lagen",
        provider="RIVM / partners",
        url="https://www.atlasleefomgeving.nl/",
        refresh_cadence="ad hoc",
        coverage="NL, per laag verschillend",
        licence="Open data (laag-specifiek)",
        notes=(
            "Alleen lagen met stabiele, downloadbare bronnen worden opgenomen. "
            "Geen runtime-afhankelijkheid van het portaal."
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
