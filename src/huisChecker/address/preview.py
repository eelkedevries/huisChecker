"""Free preview assembly.

Resolves an address via the PDOK cache (nationwide) and enriches it with local
curated datasets: BAG object attributes, postcode4 area metrics (CBS,
Leefbaarometer, police, climate), and municipality/province lookup. Addresses
outside the curated footprint still render, with a partial-preview flag and
None values where enrichment is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from huisChecker.address.search import resolve_address
from huisChecker.etl.io import read_csv
from huisChecker.etl.manifest import read_manifest


@dataclass(frozen=True)
class AddressPreview:
    address_id: str
    nummeraanduiding_id: str
    bag_object_id: str
    display_address: str
    street: str
    house_number: str
    house_number_addition: str
    postcode: str
    city: str
    postcode4: str
    municipality_code: str
    municipality_name: str
    province_code: str
    province_name: str
    construction_year: str | None
    surface_area_m2: str | None
    use_purpose: str | None
    latitude: float | None
    longitude: float | None
    population_density: str | None
    leefbaarometer_score: str | None
    leefbaarometer_band: str | None
    flood_probability_class: str | None
    heat_stress_class: str | None
    road_noise_class: str | None
    incidents_per_1000: str | None
    bag_reference_period: str
    cbs_reference_period: str
    leefbaarometer_reference_period: str
    politie_reference_period: str
    klimaat_reference_period: str
    strengths: tuple[str, ...]
    cautions: tuple[str, ...]
    is_partial: bool
    missing_layers: tuple[str, ...]


def _default_data_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def _normalise_postcode4(value: str | None) -> str:
    """Return a 4-digit PC4 code, stripped of spaces and PC6 suffixes."""
    if not value:
        return ""
    digits = "".join(ch for ch in value.strip() if ch.isdigit())
    return digits[:4]


def _index(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    idx: dict[str, dict[str, str]] = {}
    for row in rows:
        raw = (row.get(key) or "").strip()
        if not raw:
            continue
        # Postcode keys get normalised so 4-digit joins are canonical.
        canonical = _normalise_postcode4(raw) if key == "postcode4" else raw
        if canonical:
            idx[canonical] = row
    return idx


def _or_none(value: str | None) -> str | None:
    return value if value else None


def _format_use_purpose(raw: str) -> str:
    labels = {
        "woonfunctie": "wonen",
        "winkelfunctie": "winkel",
        "kantoorfunctie": "kantoor",
        "bijeenkomstfunctie": "bijeenkomst",
        "industriefunctie": "industrie",
        "logiesfunctie": "logies",
        "sportfunctie": "sport",
        "gezondheidszorgfunctie": "gezondheidszorg",
        "onderwijsfunctie": "onderwijs",
        "celfunctie": "cel",
        "overige gebruiksfunctie": "overig",
    }
    parts = [labels.get(p.strip(), p.strip()) for p in raw.split(";") if p.strip()]
    return ", ".join(parts)


def _derive_signals(
    lb_band: str | None,
    flood_class: str | None,
    heat_class: str | None,
    noise_class: str | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    strengths: list[str] = []
    cautions: list[str] = []

    if lb_band in ("goed", "zeer_goed"):
        strengths.append(
            "Leefbaarheid in dit postcodegebied scoort als goed (Leefbaarometer)."
        )
    elif lb_band in ("matig", "slecht", "zeer_slecht"):
        cautions.append(
            "Leefbaarheid in dit postcodegebied scoort als matig of lager (Leefbaarometer)."
        )

    if flood_class == "klein":
        strengths.append(
            "Relatief laag overstromingsrisico in dit postcodegebied (Klimaateffectatlas)."
        )
    elif flood_class in ("groot", "zeer_groot"):
        cautions.append(
            "Verhoogd overstromingsrisico gesignaleerd in dit postcodegebied (Klimaateffectatlas)."
        )

    if heat_class in ("groot", "zeer_groot"):
        cautions.append(
            "Verhoogde hittestress in dit postcodegebied (Klimaateffectatlas)."
        )

    if noise_class in ("hoog", "zeer_hoog"):
        cautions.append(
            "Hogere geluidbelasting langs de weg in dit postcodegebied (Atlas Leefomgeving)."
        )

    return tuple(strengths), tuple(cautions)


def _read_period(manifests_root: Path, source_key: str, fallback: str) -> str:
    manifest = read_manifest(manifests_root, source_key)
    if manifest and manifest.reference_period:
        return manifest.reference_period
    return fallback


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_csv(path)


def build_preview(address_id: str, data_root: Path | None = None) -> AddressPreview | None:
    root = data_root if data_root is not None else _default_data_root()
    curated = root / "curated"
    manifests = root / "manifests"

    resolved = resolve_address(address_id)
    if resolved is None:
        return None

    pc4_key = _normalise_postcode4(resolved.postcode4)

    bag_objects = _index(_load_csv(curated / "bag_objects.csv"), "id")
    bag = bag_objects.get(resolved.bag_object_id) if resolved.bag_object_id else None

    overview_rows = _load_csv(curated / "postcode4_overview.csv")
    overview = _index(overview_rows, "postcode4")
    pc4 = overview.get(pc4_key, {})

    # Per-module indices so missing-data messaging can be precise rather
    # than lumping every module into one blanket "Buurtcijfers" string.
    cbs_idx = _index(_load_csv(curated / "postcode4_metrics.csv"), "geography_code")
    leef_idx = _index(_load_csv(curated / "leefbaarometer_pc4.csv"), "postcode4")
    politie_idx = _index(_load_csv(curated / "politie_pc4_incidents.csv"), "postcode4")
    klimaat_idx = _index(_load_csv(curated / "klimaat_pc4.csv"), "postcode4")

    municipalities = _index(_load_csv(curated / "municipalities.csv"), "code")
    mun = municipalities.get(resolved.municipality_code, {})

    provinces = _index(_load_csv(curated / "provinces.csv"), "code")
    prov = provinces.get(resolved.province_code, {})

    display = f"{resolved.street} {resolved.house_number}".strip()
    if resolved.house_number_addition:
        display += f" {resolved.house_number_addition}"
    display += f", {resolved.city} ({resolved.postcode})"

    construction_year = _or_none(bag.get("construction_year") if bag else None)
    surface_area_m2 = _or_none(bag.get("surface_area_m2") if bag else None)
    use_purpose_raw = bag.get("use_purpose", "") if bag else ""
    use_purpose = _or_none(_format_use_purpose(use_purpose_raw))

    bag_lat: float | None = None
    bag_lon: float | None = None
    if bag:
        try:
            bag_lat = float(bag["latitude"]) if bag.get("latitude") else None
            bag_lon = float(bag["longitude"]) if bag.get("longitude") else None
        except (TypeError, ValueError):
            bag_lat = bag_lon = None
    latitude = bag_lat if bag_lat is not None else resolved.latitude
    longitude = bag_lon if bag_lon is not None else resolved.longitude

    lb_score = _or_none(pc4.get("leefbaarometer_score"))
    lb_band = _or_none(pc4.get("leefbaarometer_band"))
    flood_class = _or_none(pc4.get("flood_probability_class"))
    heat_class = _or_none(pc4.get("heat_stress_class"))
    noise_class = _or_none(pc4.get("road_noise_class"))
    incidents = _or_none(pc4.get("incidents_per_1000"))
    density = _or_none(pc4.get("population_density"))

    strengths, cautions = _derive_signals(lb_band, flood_class, heat_class, noise_class)

    missing: list[str] = []
    if bag is None:
        missing.append("BAG-gebouwgegevens")
    # Per-module coverage: check each source CSV individually so we can tell
    # the user exactly which module has no row for this postcode4.
    if pc4_key not in cbs_idx and density is None:
        missing.append("CBS kerncijfers")
    if pc4_key not in leef_idx and lb_score is None:
        missing.append("Leefbaarometer")
    if pc4_key not in politie_idx and incidents is None:
        missing.append("Politiemeldingen")
    if (
        pc4_key not in klimaat_idx
        and flood_class is None
        and heat_class is None
        and noise_class is None
    ):
        missing.append("Klimaat- en milieuklassen")
    is_partial = bool(missing)

    return AddressPreview(
        address_id=resolved.address_id,
        nummeraanduiding_id=resolved.nummeraanduiding_id,
        bag_object_id=resolved.bag_object_id,
        display_address=display,
        street=resolved.street,
        house_number=resolved.house_number,
        house_number_addition=resolved.house_number_addition,
        postcode=resolved.postcode,
        city=resolved.city,
        postcode4=pc4_key or resolved.postcode4,
        municipality_code=resolved.municipality_code,
        municipality_name=mun.get("name", resolved.municipality_name),
        province_code=resolved.province_code,
        province_name=prov.get("name", resolved.province_name),
        construction_year=construction_year,
        surface_area_m2=surface_area_m2,
        use_purpose=use_purpose,
        latitude=latitude,
        longitude=longitude,
        population_density=density,
        leefbaarometer_score=lb_score,
        leefbaarometer_band=lb_band,
        flood_probability_class=flood_class,
        heat_stress_class=heat_class,
        road_noise_class=noise_class,
        incidents_per_1000=incidents,
        bag_reference_period=_read_period(manifests, "bag", "2026-03"),
        cbs_reference_period=_read_period(manifests, "cbs_kerncijfers_pc4", "2024"),
        leefbaarometer_reference_period=_read_period(manifests, "leefbaarometer", "2022"),
        politie_reference_period=_read_period(manifests, "politie_opendata", "2025"),
        klimaat_reference_period=_read_period(manifests, "klimaateffectatlas", "2023"),
        strengths=strengths,
        cautions=cautions,
        is_partial=is_partial,
        missing_layers=tuple(missing),
    )


__all__ = ["AddressPreview", "build_preview"]
