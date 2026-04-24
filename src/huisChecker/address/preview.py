"""Free preview assembly.

Resolves an address via the PDOK cache (nationwide) and enriches it
through remote-first source adapters (CBS, BAG, politie, klimaat,
leefbaarometer). Each adapter is scope-gated via `huisChecker.scope`
so out-of-scope pc4s never trigger a remote call; when in-scope and
the remote/cache path yields nothing, adapters fall back to the
minimal local subset (curated CSV). Per-module missing-data messaging
stays precise: a section with no data from any layer is listed, but
the banner does not fire when enrichment is actually available.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from huisChecker.address.search import resolve_address
from huisChecker.etl.io import read_csv
from huisChecker.etl.manifest import read_manifest
from huisChecker.remote import bag as bag_adapter
from huisChecker.remote import cbs as cbs_adapter
from huisChecker.remote import klimaat as klimaat_adapter
from huisChecker.etl.sources.leefbaarometer import DIMENSION_KEYS as LB_DIMENSION_KEYS
from huisChecker.remote import leefbaarometer as lb_adapter
from huisChecker.remote import politie as politie_adapter
from huisChecker.scope import current_scope


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
    leefbaarometer_dimensions: tuple[tuple[str, str, str], ...]
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
    in_scope: bool
    data_sources: dict[str, str]


def _default_data_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data"


def _normalise_postcode4(value: str | None) -> str:
    if not value:
        return ""
    digits = "".join(ch for ch in value.strip() if ch.isdigit())
    return digits[:4]


_LB_DIMENSION_LABELS: dict[str, str] = {
    "woningvoorraad": "Woningvoorraad",
    "fysieke_omgeving": "Fysieke omgeving",
    "voorzieningen": "Voorzieningen",
    "sociale_samenhang": "Sociale samenhang",
    "overlast_en_onveiligheid": "Overlast en onveiligheid",
}


def _build_lb_dimensions(
    payload: dict | None,
) -> tuple[tuple[str, str, str], ...]:
    if not payload:
        return ()
    raw = payload.get("dimensions") or {}
    if not isinstance(raw, dict) or not raw:
        return ()
    out: list[tuple[str, str, str]] = []
    for key in LB_DIMENSION_KEYS:
        value = raw.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        out.append((key, _LB_DIMENSION_LABELS.get(key, key), text))
    return tuple(out)


def _or_none(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


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
        strengths.append("Leefbaarheid in dit postcodegebied scoort als goed (Leefbaarometer).")
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
        cautions.append("Verhoogde hittestress in dit postcodegebied (Klimaateffectatlas).")

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


def _index(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    idx: dict[str, dict[str, str]] = {}
    for row in rows:
        raw = (row.get(key) or "").strip()
        if not raw:
            continue
        canonical = _normalise_postcode4(raw) if key == "postcode4" else raw
        if canonical:
            idx[canonical] = row
    return idx


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
    scope = current_scope()
    in_scope = scope.covers(
        pc4=pc4_key,
        municipality=resolved.municipality_code,
        province=resolved.province_code,
    )
    sources: dict[str, str] = {}

    # --- BAG: remote adapter first, local fallback inside adapter -----------
    bag_payload = bag_adapter.fetch_object(resolved.bag_object_id, data_root=root)
    if bag_payload:
        sources["bag"] = str(bag_payload.get("source", ""))

    construction_year = _or_none(bag_payload.get("construction_year")) if bag_payload else None
    surface_area_m2 = _or_none(bag_payload.get("surface_area_m2")) if bag_payload else None
    use_purpose_raw = (bag_payload.get("use_purpose") or "") if bag_payload else ""
    use_purpose = _or_none(_format_use_purpose(use_purpose_raw))
    bag_lat = bag_payload.get("latitude") if bag_payload else None
    bag_lon = bag_payload.get("longitude") if bag_payload else None
    latitude = bag_lat if bag_lat is not None else resolved.latitude
    longitude = bag_lon if bag_lon is not None else resolved.longitude

    # --- CBS / Leefbaarometer / Politie / Klimaat via adapters --------------
    cbs_payload = cbs_adapter.fetch_pc4(pc4_key, data_root=root)
    if cbs_payload:
        sources["cbs"] = str(cbs_payload.get("source", ""))
    density = _or_none(cbs_payload.get("population_density")) if cbs_payload else None

    lb_payload = lb_adapter.fetch_pc4(pc4_key, data_root=root)
    if lb_payload:
        sources["leefbaarometer"] = str(lb_payload.get("source", ""))
    lb_score = _or_none(lb_payload.get("score")) if lb_payload else None
    lb_band = _or_none(lb_payload.get("band")) if lb_payload else None
    lb_dimensions = _build_lb_dimensions(lb_payload)

    politie_payload = politie_adapter.fetch_pc4(
        pc4_key, municipality_code=resolved.municipality_code, data_root=root
    )
    if politie_payload:
        sources["politie"] = str(politie_payload.get("source", ""))
    incidents = _or_none(politie_payload.get("incidents_per_1000")) if politie_payload else None

    klimaat_payload = klimaat_adapter.fetch_pc4(pc4_key, data_root=root)
    if klimaat_payload:
        sources["klimaat"] = str(klimaat_payload.get("source", ""))
    kp = klimaat_payload or {}
    flood_class = _or_none(kp.get("flood_probability_class"))
    heat_class = _or_none(kp.get("heat_stress_class"))
    noise_class = _or_none(kp.get("road_noise_class"))

    # --- Municipality / province naming from the minimal subset -------------
    municipalities = _index(_load_csv(curated / "municipalities.csv"), "code")
    mun = municipalities.get(resolved.municipality_code, {})
    provinces = _index(_load_csv(curated / "provinces.csv"), "code")
    prov = provinces.get(resolved.province_code, {})

    display = f"{resolved.street} {resolved.house_number}".strip()
    if resolved.house_number_addition:
        display += f" {resolved.house_number_addition}"
    display += f", {resolved.city} ({resolved.postcode})"

    strengths, cautions = _derive_signals(lb_band, flood_class, heat_class, noise_class)

    # Per-module coverage: only flag modules that returned no data at all.
    missing: list[str] = []
    if bag_payload is None:
        missing.append("BAG-gebouwgegevens")
    if density is None:
        missing.append("CBS kerncijfers")
    if lb_score is None and lb_band is None:
        missing.append("Leefbaarometer")
    if incidents is None:
        missing.append("Politiemeldingen")
    if flood_class is None and heat_class is None and noise_class is None:
        missing.append("Klimaat- en milieuklassen")

    # Banner fires only when *every* module is empty.
    all_empty = len(missing) == 5
    is_partial = all_empty or (bool(missing) and not any((
        density, lb_score, lb_band, incidents, flood_class, heat_class, noise_class,
        construction_year, surface_area_m2, use_purpose,
    )))

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
        leefbaarometer_dimensions=lb_dimensions,
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
        in_scope=in_scope,
        data_sources=sources,
    )


__all__ = ["AddressPreview", "build_preview"]
