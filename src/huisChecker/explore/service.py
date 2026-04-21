"""Explore data service — loads fixture data and produces area summaries.

Reads from bundled fixture JSONs so the Explore flow works without
running the ETL pipeline first. All numbers are precomputed or derived
in-memory from the same fixture data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_FIXTURES = Path(__file__).resolve().parents[1] / "etl" / "fixtures"

_BAND_LABELS: dict[str, str] = {
    "goed": "Goed",
    "voldoende": "Voldoende",
    "matig": "Matig",
    "onvoldoende": "Onvoldoende",
    "slecht": "Slecht",
}

_CLASS_LABELS: dict[str, str] = {
    "klein": "Klein",
    "middelgroot": "Middelgroot",
    "groot": "Groot",
    "zeer_groot": "Zeer groot",
    "laag": "Laag",
    "middelmatig": "Middelmatig",
    "hoog": "Hoog",
    "zeer_hoog": "Zeer hoog",
}


def _label(key: str) -> str:
    return _BAND_LABELS.get(key) or _CLASS_LABELS.get(key) or key


def _benchmark(value: float, avg: float, higher_better: bool) -> str:
    """Return above/around/below label relative to national average."""
    if higher_better:
        if value > avg * 1.10:
            return "boven gemiddelde"
        if value < avg * 0.90:
            return "onder gemiddelde"
        return "rond gemiddelde"
    else:
        if value < avg * 0.90:
            return "beter dan gemiddeld"
        if value > avg * 1.10:
            return "slechter dan gemiddeld"
        return "rond gemiddelde"


def _benchmark_css(label: str) -> str:
    """Tailwind badge colour for benchmark label."""
    if label in ("boven gemiddelde", "beter dan gemiddeld"):
        return "bg-green-100 text-green-800"
    if label in ("onder gemiddelde", "slechter dan gemiddeld"):
        return "bg-amber-100 text-amber-800"
    return "bg-slate-100 text-slate-600"


@lru_cache(maxsize=1)
def _raw() -> dict:
    cbs = json.loads((_FIXTURES / "cbs_pc4.json").read_text())
    lb = json.loads((_FIXTURES / "leefbaarometer.json").read_text())
    pol = json.loads((_FIXTURES / "politie.json").read_text())
    klim = json.loads((_FIXTURES / "klimaat.json").read_text())

    provinces = {r["code"]: r for r in cbs["provinces"]}
    municipalities = {r["code"]: r for r in cbs["municipalities"]}
    pc4_areas = {r["code"]: r for r in cbs["postcode4_areas"]}

    pc4_cbs = {r["postcode4"]: r for r in cbs["pc4_metrics"]}
    muni_pop = {r["municipality_code"]: r["population"] for r in cbs["municipality_metrics"]}
    province_pop = {r["province_code"]: r["population"] for r in cbs["province_metrics"]}

    lb_by_pc4 = {r["postcode4"]: r for r in lb["pc4_scores"]}
    pol_by_pc4 = {r["postcode4"]: r for r in pol["pc4_incidents"]}
    flood_by_pc4 = {r["postcode4"]: r["class"] for r in klim["flood_probability_pc4"]}
    heat_by_pc4 = {r["postcode4"]: r["class"] for r in klim["heat_stress_pc4"]}
    noise_by_pc4 = {
        r["postcode4"]: r["road_noise_class"] for r in klim["atlas_leefomgeving_noise_pc4"]
    }

    # incidents per 1000 from politie + CBS population
    inc_per_1000: dict[str, float] = {}
    for pc4, pol_row in pol_by_pc4.items():
        cbs_row = pc4_cbs.get(pc4)
        if cbs_row and cbs_row["population"] > 0:
            inc_per_1000[pc4] = pol_row["total_incidents"] / cbs_row["population"] * 1000

    # national averages for benchmarking
    all_density = [r["population_density"] for r in cbs["pc4_metrics"]]
    all_lb = [r["score"] for r in lb["pc4_scores"]]
    all_inc = list(inc_per_1000.values())

    nat_avg_density = sum(all_density) / len(all_density) if all_density else None
    nat_avg_lb = sum(all_lb) / len(all_lb) if all_lb else None
    nat_avg_inc = sum(all_inc) / len(all_inc) if all_inc else None

    return dict(
        provinces=provinces,
        municipalities=municipalities,
        pc4_areas=pc4_areas,
        pc4_cbs=pc4_cbs,
        muni_pop=muni_pop,
        province_pop=province_pop,
        lb_by_pc4=lb_by_pc4,
        flood_by_pc4=flood_by_pc4,
        heat_by_pc4=heat_by_pc4,
        noise_by_pc4=noise_by_pc4,
        inc_per_1000=inc_per_1000,
        nat_avg_density=nat_avg_density,
        nat_avg_lb=nat_avg_lb,
        nat_avg_inc=nat_avg_inc,
        periods=dict(
            cbs=cbs["reference_period"],
            leefbaarometer=lb["reference_period"],
            politie=pol["reference_period"],
            klimaat=klim["reference_period"],
        ),
    )


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------


@dataclass
class ProvinceRow:
    code: str
    name: str
    population: int
    municipality_count: int


@dataclass
class MunicipalityRow:
    code: str
    name: str
    province_code: str
    population: int | None
    pc4_count: int
    avg_lb_score: float | None
    avg_lb_band: str | None
    avg_inc_per_1000: float | None
    inc_benchmark: str | None
    inc_benchmark_css: str


@dataclass
class Postcode4Row:
    code: str
    municipality_code: str
    municipality_name: str
    province_code: str
    province_name: str
    # leefbaarheid
    lb_score: float | None
    lb_band: str | None
    lb_band_label: str | None
    lb_benchmark: str | None
    lb_benchmark_css: str
    # density
    population_density: float | None
    density_benchmark: str | None
    density_benchmark_css: str
    # safety
    inc_per_1000: float | None
    inc_benchmark: str | None
    inc_benchmark_css: str
    # climate
    flood_class: str | None
    flood_class_label: str | None
    heat_class: str | None
    heat_class_label: str | None
    noise_class: str | None
    noise_class_label: str | None
    # source periods
    periods: dict[str, str]


def province_list() -> list[ProvinceRow]:
    d = _raw()
    rows = []
    for code, prov in d["provinces"].items():
        muni_codes = [c for c, m in d["municipalities"].items() if m["province_code"] == code]
        rows.append(
            ProvinceRow(
                code=code,
                name=prov["name"],
                population=d["province_pop"].get(code, 0),
                municipality_count=len(muni_codes),
            )
        )
    return sorted(rows, key=lambda r: r.name)


def municipality_list(province_code: str) -> list[MunicipalityRow] | None:
    d = _raw()
    if province_code not in d["provinces"]:
        return None
    munis = [m for m in d["municipalities"].values() if m["province_code"] == province_code]
    rows = []
    for m in munis:
        pc4s = [c for c, a in d["pc4_areas"].items() if a["municipality_code"] == m["code"]]
        lb_scores = [d["lb_by_pc4"][p]["score"] for p in pc4s if p in d["lb_by_pc4"]]
        inc_vals = [d["inc_per_1000"][p] for p in pc4s if p in d["inc_per_1000"]]

        avg_lb = sum(lb_scores) / len(lb_scores) if lb_scores else None
        avg_inc = sum(inc_vals) / len(inc_vals) if inc_vals else None

        # majority band from lb scores
        if avg_lb is not None:
            if avg_lb >= 6.5:
                avg_band = "Goed"
            elif avg_lb >= 5.5:
                avg_band = "Voldoende"
            elif avg_lb >= 4.5:
                avg_band = "Matig"
            else:
                avg_band = "Onvoldoende"
        else:
            avg_band = None

        inc_bm = None
        inc_bm_css = "bg-slate-100 text-slate-600"
        nat = d["nat_avg_inc"]
        if avg_inc is not None and nat is not None:
            inc_bm = _benchmark(avg_inc, nat, higher_better=False)
            inc_bm_css = _benchmark_css(inc_bm)

        rows.append(
            MunicipalityRow(
                code=m["code"],
                name=m["name"],
                province_code=m["province_code"],
                population=d["muni_pop"].get(m["code"]),
                pc4_count=len(pc4s),
                avg_lb_score=round(avg_lb, 1) if avg_lb is not None else None,
                avg_lb_band=avg_band,
                avg_inc_per_1000=round(avg_inc, 1) if avg_inc is not None else None,
                inc_benchmark=inc_bm,
                inc_benchmark_css=inc_bm_css,
            )
        )
    return sorted(rows, key=lambda r: r.name)


def postcode4_list(municipality_code: str) -> list[Postcode4Row] | None:
    d = _raw()
    if municipality_code not in d["municipalities"]:
        return None
    pc4_codes = [
        c for c, a in d["pc4_areas"].items() if a["municipality_code"] == municipality_code
    ]
    rows = []
    for pc4 in sorted(pc4_codes):
        rows.append(_build_pc4_row(pc4, d))
    return rows


def postcode4_detail(pc4_code: str) -> Postcode4Row | None:
    d = _raw()
    if pc4_code not in d["pc4_areas"]:
        return None
    return _build_pc4_row(pc4_code, d)


def _build_pc4_row(pc4: str, d: dict) -> Postcode4Row:
    area = d["pc4_areas"][pc4]
    muni = d["municipalities"].get(area["municipality_code"], {})
    prov = d["provinces"].get(area["province_code"], {})

    lb = d["lb_by_pc4"].get(pc4)
    lb_score = lb["score"] if lb else None
    lb_band = lb["band"] if lb else None

    cbs_row = d["pc4_cbs"].get(pc4)
    density = cbs_row["population_density"] if cbs_row else None

    inc = d["inc_per_1000"].get(pc4)

    # benchmarks
    lb_bm = lb_bm_css = None
    if lb_score is not None and d["nat_avg_lb"] is not None:
        lb_bm = _benchmark(lb_score, d["nat_avg_lb"], higher_better=True)
        lb_bm_css = _benchmark_css(lb_bm)
    else:
        lb_bm_css = "bg-slate-100 text-slate-600"

    den_bm = den_bm_css = None
    if density is not None and d["nat_avg_density"] is not None:
        den_bm = _benchmark(density, d["nat_avg_density"], higher_better=True)
        den_bm_css = _benchmark_css(den_bm)
    else:
        den_bm_css = "bg-slate-100 text-slate-600"

    inc_bm = inc_bm_css = None
    if inc is not None and d["nat_avg_inc"] is not None:
        inc_bm = _benchmark(inc, d["nat_avg_inc"], higher_better=False)
        inc_bm_css = _benchmark_css(inc_bm)
    else:
        inc_bm_css = "bg-slate-100 text-slate-600"

    flood = d["flood_by_pc4"].get(pc4)
    heat = d["heat_by_pc4"].get(pc4)
    noise = d["noise_by_pc4"].get(pc4)

    return Postcode4Row(
        code=pc4,
        municipality_code=area["municipality_code"],
        municipality_name=muni.get("name", area["municipality_code"]),
        province_code=area["province_code"],
        province_name=prov.get("name", area["province_code"]),
        lb_score=lb_score,
        lb_band=lb_band,
        lb_band_label=_label(lb_band) if lb_band else None,
        lb_benchmark=lb_bm,
        lb_benchmark_css=lb_bm_css or "bg-slate-100 text-slate-600",
        population_density=round(density, 0) if density is not None else None,
        density_benchmark=den_bm,
        density_benchmark_css=den_bm_css or "bg-slate-100 text-slate-600",
        inc_per_1000=round(inc, 1) if inc is not None else None,
        inc_benchmark=inc_bm,
        inc_benchmark_css=inc_bm_css or "bg-slate-100 text-slate-600",
        flood_class=flood,
        flood_class_label=_label(flood) if flood else None,
        heat_class=heat,
        heat_class_label=_label(heat) if heat else None,
        noise_class=noise,
        noise_class_label=_label(noise) if noise else None,
        periods=d["periods"],
    )


def province_name(code: str) -> str | None:
    d = _raw()
    prov = d["provinces"].get(code)
    return prov["name"] if prov else None


def municipality_name(code: str) -> str | None:
    d = _raw()
    muni = d["municipalities"].get(code)
    return muni["name"] if muni else None


__all__ = [
    "MunicipalityRow",
    "Postcode4Row",
    "ProvinceRow",
    "municipality_list",
    "municipality_name",
    "postcode4_detail",
    "postcode4_list",
    "province_list",
    "province_name",
]
