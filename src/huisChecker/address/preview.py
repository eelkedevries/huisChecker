"""Free preview assembly: joins address to BAG, area metrics, and geography."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from huisChecker.etl.io import read_csv
from huisChecker.etl.manifest import read_manifest


@dataclass(frozen=True)
class AddressPreview:
    address_id: str
    display_address: str
    street: str
    house_number: str
    house_number_addition: str
    postcode: str
    city: str
    postcode4: str
    municipality_name: str
    province_name: str
    # Building
    construction_year: str | None
    surface_area_m2: str | None
    use_purpose: str | None
    latitude: float | None
    longitude: float | None
    # Area metrics
    population_density: str | None
    leefbaarometer_score: str | None
    leefbaarometer_band: str | None
    flood_probability_class: str | None
    heat_stress_class: str | None
    road_noise_class: str | None
    incidents_per_1000: str | None
    # Source reference periods
    bag_reference_period: str
    cbs_reference_period: str
    leefbaarometer_reference_period: str
    politie_reference_period: str
    klimaat_reference_period: str
    # Derived signals
    strengths: tuple[str, ...]
    cautions: tuple[str, ...]


def _default_data_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def _index(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in rows if row.get(key)}


def _or_none(value: str | None) -> str | None:
    return value if value else None


def _as_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def build_preview(address_id: str, data_root: Path | None = None) -> AddressPreview | None:
    root = data_root if data_root is not None else _default_data_root()
    curated = root / "curated"
    manifests = root / "manifests"

    if not (curated / "addresses.csv").exists():
        return None

    addresses = _index(read_csv(curated / "addresses.csv"), "id")
    addr = addresses.get(address_id)
    if addr is None:
        return None

    bag_objects = _index(read_csv(curated / "bag_objects.csv"), "id")
    bag = bag_objects.get(addr.get("bag_object_id", ""))

    overview = _index(read_csv(curated / "postcode4_overview.csv"), "postcode4")
    pc4 = overview.get(addr["postcode4"], {})

    municipalities = _index(read_csv(curated / "municipalities.csv"), "code")
    mun = municipalities.get(addr["municipality_code"], {})

    provinces = _index(read_csv(curated / "provinces.csv"), "code")
    prov = provinces.get(addr["province_code"], {})

    display = f"{addr['street']} {addr['house_number']}"
    if addr.get("house_number_addition"):
        display += f" {addr['house_number_addition']}"
    display += f", {addr['city']} ({addr['postcode']})"

    construction_year = _or_none(bag.get("construction_year") if bag else None)
    surface_area_m2 = _or_none(bag.get("surface_area_m2") if bag else None)
    use_purpose_raw = bag.get("use_purpose", "") if bag else ""
    use_purpose = _or_none(_format_use_purpose(use_purpose_raw))
    latitude = _as_float(bag.get("latitude") if bag else None)
    longitude = _as_float(bag.get("longitude") if bag else None)

    lb_score = _or_none(pc4.get("leefbaarometer_score"))
    lb_band = _or_none(pc4.get("leefbaarometer_band"))
    flood_class = _or_none(pc4.get("flood_probability_class"))
    heat_class = _or_none(pc4.get("heat_stress_class"))
    noise_class = _or_none(pc4.get("road_noise_class"))
    incidents = _or_none(pc4.get("incidents_per_1000"))
    density = _or_none(pc4.get("population_density"))

    strengths, cautions = _derive_signals(lb_band, flood_class, heat_class, noise_class)

    return AddressPreview(
        address_id=address_id,
        display_address=display,
        street=addr["street"],
        house_number=addr["house_number"],
        house_number_addition=addr.get("house_number_addition", ""),
        postcode=addr["postcode"],
        city=addr["city"],
        postcode4=addr["postcode4"],
        municipality_name=mun.get("name", addr["municipality_code"]),
        province_name=prov.get("name", addr["province_code"]),
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
    )


__all__ = ["AddressPreview", "build_preview"]
