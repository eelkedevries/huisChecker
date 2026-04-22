"""Full report assembly for the paid output.

Produces a structured `FullReport` per address by joining the curated
postcode4 overview, BAG facts, and source manifests. Computes municipality,
province, and national benchmarks for numeric metrics on the fly so that
the report is self-contained and source-transparent. Source-native scores
(Leefbaarometer band, climate class) are shown as published; no opaque
composite score is constructed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from huisChecker.address.preview import AddressPreview, build_preview
from huisChecker.etl.io import read_csv
from huisChecker.etl.manifest import read_manifest
from huisChecker.etl.sources.registry import source_registry
from huisChecker.report.modules import ReportModuleKey, report_module_registry

GLOBAL_CAVEAT = (
    "Dit rapport bundelt publieke databronnen op postcodegebied-niveau. "
    "Geen enkele bron dekt alles; de sectiekanttekeningen blijven leidend. "
    "Er wordt geen samengestelde 'huisChecker-score' berekend."
)


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FindingRow:
    label: str
    value: str | None
    unit: str | None = None
    comparison_label: str | None = None
    comparison_css: str = "bg-slate-100 text-slate-600"
    comparison_detail: str | None = None
    caveat: str | None = None


@dataclass(frozen=True)
class ReportSection:
    key: str
    label: str
    description: str
    summary: str
    findings: tuple[FindingRow, ...]
    caveat: str
    source_dataset_keys: tuple[str, ...]
    layer_keys: tuple[str, ...]


@dataclass(frozen=True)
class SourceListing:
    key: str
    label: str
    provider: str
    url: str | None
    licence: str | None
    reference_period: str | None
    refresh_cadence: str
    notes: str | None
    caveats: tuple[str, ...]


@dataclass(frozen=True)
class FullReport:
    address_id: str
    display_address: str
    street: str
    house_number: str
    house_number_addition: str
    postcode: str
    postcode4: str
    city: str
    municipality_name: str
    province_name: str
    construction_year: str | None
    surface_area_m2: str | None
    use_purpose: str | None
    latitude: float | None
    longitude: float | None
    generated_at: str
    executive_summary: tuple[str, ...]
    positives: tuple[str, ...]
    cautions: tuple[str, ...]
    sections: tuple[ReportSection, ...] = field(default_factory=tuple)
    sources: tuple[SourceListing, ...] = field(default_factory=tuple)
    global_caveat: str = GLOBAL_CAVEAT


# ---------------------------------------------------------------------------
# Loading and aggregation
# ---------------------------------------------------------------------------


def _default_data_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class _Aggregates:
    by_pc4: dict[str, dict[str, str]]
    municipal_avg: dict[str, dict[str, float]]
    provincial_avg: dict[str, dict[str, float]]
    national_avg: dict[str, float]


_NUMERIC_FIELDS = (
    "population_density",
    "leefbaarometer_score",
    "incidents_per_1000",
)


def _aggregate(rows: Iterable[dict[str, str]]) -> _Aggregates:
    rows = list(rows)
    by_pc4 = {row["postcode4"]: row for row in rows}

    def avg(group_key: str) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, list[float]]] = {}
        for row in rows:
            g = row.get(group_key) or ""
            if not g:
                continue
            bucket = out.setdefault(g, {f: [] for f in _NUMERIC_FIELDS})
            for f in _NUMERIC_FIELDS:
                v = _to_float(row.get(f))
                if v is not None:
                    bucket[f].append(v)
        return {
            g: {f: sum(vals) / len(vals) for f, vals in by_field.items() if vals}
            for g, by_field in out.items()
        }

    municipal = avg("municipality_code")
    provincial = avg("province_code")

    national: dict[str, float] = {}
    for f in _NUMERIC_FIELDS:
        vals = [v for v in (_to_float(r.get(f)) for r in rows) if v is not None]
        if vals:
            national[f] = sum(vals) / len(vals)

    return _Aggregates(by_pc4, municipal, provincial, national)


# ---------------------------------------------------------------------------
# Benchmark helpers
# ---------------------------------------------------------------------------


def _benchmark(value: float, reference: float, *, higher_better: bool) -> str:
    if higher_better:
        if value > reference * 1.10:
            return "boven gemiddelde"
        if value < reference * 0.90:
            return "onder gemiddelde"
        return "rond gemiddelde"
    if value < reference * 0.90:
        return "beter dan gemiddeld"
    if value > reference * 1.10:
        return "slechter dan gemiddeld"
    return "rond gemiddelde"


def _benchmark_css(label: str | None) -> str:
    if label in ("boven gemiddelde", "beter dan gemiddeld"):
        return "bg-green-100 text-green-800"
    if label in ("onder gemiddelde", "slechter dan gemiddeld"):
        return "bg-amber-100 text-amber-800"
    return "bg-slate-100 text-slate-600"


def _format_number(value: float | None, *, decimals: int = 0) -> str | None:
    if value is None:
        return None
    return f"{value:,.{decimals}f}".replace(",", ".")


def _format_class(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("_", " ")


def _comparison_detail(
    pc4_value: float | None,
    *,
    municipality_value: float | None,
    province_value: float | None,
    national_value: float | None,
    municipality_name: str,
    province_name: str,
    decimals: int,
    unit: str | None,
) -> str | None:
    parts: list[str] = []
    if pc4_value is None:
        return None
    if municipality_value is not None:
        parts.append(
            f"{municipality_name}: {_format_number(municipality_value, decimals=decimals)}"
            f"{(' ' + unit) if unit else ''}"
        )
    if province_value is not None:
        parts.append(
            f"{province_name}: {_format_number(province_value, decimals=decimals)}"
            f"{(' ' + unit) if unit else ''}"
        )
    if national_value is not None:
        parts.append(
            f"Nederland: {_format_number(national_value, decimals=decimals)}"
            f"{(' ' + unit) if unit else ''}"
        )
    return " · ".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _building_section(preview: AddressPreview) -> ReportSection:
    contract = report_module_registry.get(ReportModuleKey.BUILDING_BASICS)
    findings: list[FindingRow] = []
    if preview.construction_year:
        findings.append(
            FindingRow(
                label="Bouwjaar (BAG)",
                value=preview.construction_year,
                unit=None,
                caveat="Renovaties en latere ingrepen zijn niet zichtbaar in BAG.",
            )
        )
    if preview.surface_area_m2:
        findings.append(
            FindingRow(
                label="Gebruiksoppervlak",
                value=preview.surface_area_m2,
                unit="m²",
            )
        )
    if preview.use_purpose:
        findings.append(
            FindingRow(
                label="Gebruiksfunctie",
                value=preview.use_purpose,
            )
        )

    if findings:
        parts = [
            f"{f.label.lower()} {f.value}{(' ' + f.unit) if f.unit else ''}" for f in findings
        ]
        summary = "Verblijfsobject geregistreerd in BAG met " + ", ".join(parts) + "."
    else:
        summary = "Geen BAG-kenmerken beschikbaar voor dit adres."

    return ReportSection(
        key=contract.key.value,
        label=contract.label,
        description=contract.description,
        summary=summary,
        findings=tuple(findings),
        caveat=contract.caveat,
        source_dataset_keys=contract.source_dataset_keys,
        layer_keys=contract.layer_keys,
    )


def _area_section(
    preview: AddressPreview,
    agg: _Aggregates,
    *,
    municipality_code: str,
    province_code: str,
) -> ReportSection:
    contract = report_module_registry.get(ReportModuleKey.AREA_PROFILE)
    pc4_row = agg.by_pc4.get(preview.postcode4, {})
    density = _to_float(pc4_row.get("population_density"))
    muni = agg.municipal_avg.get(municipality_code, {})
    prov = agg.provincial_avg.get(province_code, {})

    findings: list[FindingRow] = []
    if density is not None:
        national = agg.national_avg.get("population_density")
        bm_label = _benchmark(density, national, higher_better=True) if national else None
        findings.append(
            FindingRow(
                label="Bevolkingsdichtheid",
                value=_format_number(density, decimals=0),
                unit="inwoners/km²",
                comparison_label=bm_label,
                comparison_css=_benchmark_css(bm_label),
                comparison_detail=_comparison_detail(
                    density,
                    municipality_value=muni.get("population_density"),
                    province_value=prov.get("population_density"),
                    national_value=national,
                    municipality_name=preview.municipality_name,
                    province_name=preview.province_name,
                    decimals=0,
                    unit="inwoners/km²",
                ),
                caveat="CBS PC4-snapshot; gemiddelde over het postcodegebied.",
            )
        )

    summary = (
        f"Postcodegebied {preview.postcode4} ligt in {preview.municipality_name} "
        f"({preview.province_name}). "
        + (
            f"Bevolkingsdichtheid is {findings[0].comparison_label or '—'} "
            f"vergeleken met het Nederlandse gemiddelde."
            if findings
            else "Geen demografische kerncijfers beschikbaar voor dit gebied."
        )
    )

    return ReportSection(
        key=contract.key.value,
        label=contract.label,
        description=contract.description,
        summary=summary,
        findings=tuple(findings),
        caveat=contract.caveat,
        source_dataset_keys=contract.source_dataset_keys,
        layer_keys=contract.layer_keys,
    )


def _liveability_section(preview: AddressPreview) -> ReportSection:
    contract = report_module_registry.get(ReportModuleKey.LIVEABILITY)
    findings: list[FindingRow] = []
    if preview.leefbaarometer_score:
        band = _format_class(preview.leefbaarometer_band)
        findings.append(
            FindingRow(
                label="Leefbaarometer-score",
                value=preview.leefbaarometer_score,
                unit=None,
                comparison_label=band,
                comparison_css=_benchmark_css(None),
                comparison_detail=(
                    "Bron-eigen klasse-indeling; niet hercombineren met andere indicatoren."
                ),
                caveat="Composite score van Leefbaarometer; getoond zoals gepubliceerd.",
            )
        )

    summary = (
        f"Leefbaarheid scoort als '{_format_class(preview.leefbaarometer_band)}' "
        f"in het postcodegebied (Leefbaarometer)."
        if preview.leefbaarometer_band
        else "Geen Leefbaarometer-score beschikbaar voor dit gebied."
    )

    return ReportSection(
        key=contract.key.value,
        label=contract.label,
        description=contract.description,
        summary=summary,
        findings=tuple(findings),
        caveat=contract.caveat,
        source_dataset_keys=contract.source_dataset_keys,
        layer_keys=contract.layer_keys,
    )


def _safety_section(
    preview: AddressPreview,
    agg: _Aggregates,
    *,
    municipality_code: str,
    province_code: str,
) -> ReportSection:
    contract = report_module_registry.get(ReportModuleKey.SAFETY_NUISANCE)
    pc4_row = agg.by_pc4.get(preview.postcode4, {})
    inc = _to_float(pc4_row.get("incidents_per_1000"))
    muni = agg.municipal_avg.get(municipality_code, {})
    prov = agg.provincial_avg.get(province_code, {})

    findings: list[FindingRow] = []
    if inc is not None:
        national = agg.national_avg.get("incidents_per_1000")
        bm_label = _benchmark(inc, national, higher_better=False) if national else None
        findings.append(
            FindingRow(
                label="Geregistreerde politiemeldingen",
                value=_format_number(inc, decimals=1),
                unit="per 1.000 inwoners",
                comparison_label=bm_label,
                comparison_css=_benchmark_css(bm_label),
                comparison_detail=_comparison_detail(
                    inc,
                    municipality_value=muni.get("incidents_per_1000"),
                    province_value=prov.get("incidents_per_1000"),
                    national_value=national,
                    municipality_name=preview.municipality_name,
                    province_name=preview.province_name,
                    decimals=1,
                    unit="per 1.000",
                ),
                caveat=(
                    "Alleen geregistreerde meldingen; "
                    "onder-rapportage varieert per type incident."
                ),
            )
        )

    summary = (
        f"Politiemeldingen per 1.000 inwoners liggen "
        f"{findings[0].comparison_label or 'rond gemiddelde'} ten opzichte van "
        f"het Nederlandse gemiddelde."
        if findings
        else "Geen politiemelding-cijfers beschikbaar voor dit postcodegebied."
    )

    return ReportSection(
        key=contract.key.value,
        label=contract.label,
        description=contract.description,
        summary=summary,
        findings=tuple(findings),
        caveat=contract.caveat,
        source_dataset_keys=contract.source_dataset_keys,
        layer_keys=contract.layer_keys,
    )


def _env_section(preview: AddressPreview) -> ReportSection:
    contract = report_module_registry.get(ReportModuleKey.ENV_CLIMATE)
    findings: list[FindingRow] = []
    if preview.flood_probability_class:
        findings.append(
            FindingRow(
                label="Overstromingskans",
                value=_format_class(preview.flood_probability_class),
                comparison_label="bron-eigen klasse",
                comparison_css=_benchmark_css(None),
                comparison_detail="Klimaateffectatlas, scenario-gebaseerde modellering.",
                caveat="Houdt geen rekening met gebouw-eigen waterkeringen.",
            )
        )
    if preview.heat_stress_class:
        findings.append(
            FindingRow(
                label="Hittestress",
                value=_format_class(preview.heat_stress_class),
                comparison_label="bron-eigen klasse",
                comparison_css=_benchmark_css(None),
                comparison_detail="Klimaateffectatlas, modeluitkomst op postcodegebied.",
                caveat="Klassen, geen precieze temperatuurschattingen.",
            )
        )
    if preview.road_noise_class:
        findings.append(
            FindingRow(
                label="Geluidsbelasting weg",
                value=_format_class(preview.road_noise_class),
                comparison_label="bron-eigen klasse",
                comparison_css=_benchmark_css(None),
                comparison_detail="Atlas Leefomgeving wegverkeer.",
                caveat="Modelmatige geluidsbelasting; piekbelasting kan afwijken.",
            )
        )

    if findings:
        summary = (
            "Klimaat- en milieurisico's worden weergegeven met de bron-eigen "
            "klasse-indeling van Klimaateffectatlas en Atlas Leefomgeving."
        )
    else:
        summary = "Geen klimaat- of milieurisicoklassen beschikbaar voor dit gebied."

    return ReportSection(
        key=contract.key.value,
        label=contract.label,
        description=contract.description,
        summary=summary,
        findings=tuple(findings),
        caveat=contract.caveat,
        source_dataset_keys=contract.source_dataset_keys,
        layer_keys=contract.layer_keys,
    )


def _sources_section(used_keys: Iterable[str]) -> ReportSection:
    contract = report_module_registry.get(ReportModuleKey.CAVEATS_SOURCES)
    return ReportSection(
        key=contract.key.value,
        label=contract.label,
        description=contract.description,
        summary=(
            "Hieronder staan alle gebruikte databronnen, peildatums en kanttekeningen "
            "die de basis vormen van dit rapport."
        ),
        findings=(),
        caveat=contract.caveat,
        source_dataset_keys=tuple(used_keys),
        layer_keys=(),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_full_report(
    address_id: str, data_root: Path | None = None
) -> FullReport | None:
    root = data_root if data_root is not None else _default_data_root()
    curated = root / "curated"
    manifests = root / "manifests"

    preview = build_preview(address_id, data_root=root)
    if preview is None:
        return None

    municipality_code = preview.municipality_code
    province_code = preview.province_code

    overview_path = curated / "postcode4_overview.csv"
    overview_rows = read_csv(overview_path) if overview_path.exists() else []
    agg = _aggregate(overview_rows)

    sections: list[ReportSection] = [
        _building_section(preview),
        _area_section(
            preview, agg, municipality_code=municipality_code, province_code=province_code
        ),
        _liveability_section(preview),
        _safety_section(
            preview, agg, municipality_code=municipality_code, province_code=province_code
        ),
        _env_section(preview),
    ]

    used_source_keys: list[str] = []
    seen: set[str] = set()
    for section in sections:
        for k in section.source_dataset_keys:
            if k not in seen:
                seen.add(k)
                used_source_keys.append(k)

    sources = _build_source_listings(used_source_keys, manifests)

    sections.append(_sources_section(used_source_keys))

    executive_summary = _executive_summary(preview, sections)
    positives = preview.strengths
    cautions = preview.cautions

    return FullReport(
        address_id=preview.address_id,
        display_address=preview.display_address,
        street=preview.street,
        house_number=preview.house_number,
        house_number_addition=preview.house_number_addition,
        postcode=preview.postcode,
        postcode4=preview.postcode4,
        city=preview.city,
        municipality_name=preview.municipality_name,
        province_name=preview.province_name,
        construction_year=preview.construction_year,
        surface_area_m2=preview.surface_area_m2,
        use_purpose=preview.use_purpose,
        latitude=preview.latitude,
        longitude=preview.longitude,
        generated_at=datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC"),
        executive_summary=executive_summary,
        positives=positives,
        cautions=cautions,
        sections=tuple(sections),
        sources=sources,
    )


def _build_source_listings(
    used_keys: Iterable[str], manifests_root: Path
) -> tuple[SourceListing, ...]:
    listings: list[SourceListing] = []
    for key in used_keys:
        try:
            ds = source_registry.get(key)
        except KeyError:
            continue
        manifest = read_manifest(manifests_root, key)
        listings.append(
            SourceListing(
                key=ds.key,
                label=ds.label,
                provider=ds.provider,
                url=str(ds.url) if ds.url else None,
                licence=manifest.licence if manifest else ds.licence,
                reference_period=manifest.reference_period if manifest else None,
                refresh_cadence=ds.refresh_cadence,
                notes=ds.notes,
                caveats=manifest.caveats if manifest else (),
            )
        )
    return tuple(listings)


def _executive_summary(
    preview: AddressPreview, sections: Iterable[ReportSection]
) -> tuple[str, ...]:
    bullets: list[str] = [
        f"Adres: {preview.display_address}.",
    ]
    section_map = {s.key: s for s in sections}

    area = section_map.get(ReportModuleKey.AREA_PROFILE.value)
    if area and area.findings:
        bullets.append(f"Gebied: {area.summary}")

    live = section_map.get(ReportModuleKey.LIVEABILITY.value)
    if live and live.findings:
        bullets.append(f"Leefbaarheid: {live.summary}")

    safety = section_map.get(ReportModuleKey.SAFETY_NUISANCE.value)
    if safety and safety.findings:
        bullets.append(f"Veiligheid: {safety.summary}")

    env = section_map.get(ReportModuleKey.ENV_CLIMATE.value)
    if env and env.findings:
        bullets.append(
            "Klimaat: bron-eigen klassen voor overstromingskans, hittestress en "
            "geluidsbelasting zijn opgenomen."
        )

    bullets.append(
        "Geen samengestelde score: weeg de secties zelf op basis van uw eigen prioriteiten."
    )
    return tuple(bullets)


__all__ = [
    "FindingRow",
    "FullReport",
    "GLOBAL_CAVEAT",
    "ReportSection",
    "SourceListing",
    "build_full_report",
]
