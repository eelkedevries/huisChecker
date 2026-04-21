"""Cross-source curated outputs built after source jobs have run.

Currently produces a unified `postcode4_overview.csv` that the report
and area pages can read as a single join-ready table. Deliberately kept
narrow: no composite scoring, no opinionated ranking.
"""

from __future__ import annotations

from pathlib import Path

from huisChecker.etl.io import read_csv, write_csv


def build_area_rollups(curated_root: Path) -> Path:
    pc4_areas = read_csv(curated_root / "postcode4_areas.csv")
    lb = {row["postcode4"]: row for row in read_csv(curated_root / "leefbaarometer_pc4.csv")}
    klimaat = {row["postcode4"]: row for row in read_csv(curated_root / "klimaat_pc4.csv")}
    politie = {
        row["postcode4"]: row
        for row in read_csv(curated_root / "politie_pc4_incidents.csv")
    }
    metrics_rows = read_csv(curated_root / "postcode4_metrics.csv")
    density_by_pc4 = {
        row["geography_code"]: row["value"]
        for row in metrics_rows
        if row["metric_key"] == "cbs_population_density"
    }

    rows = []
    for area in pc4_areas:
        pc4 = area["code"]
        rows.append(
            {
                "postcode4": pc4,
                "municipality_code": area["municipality_code"],
                "province_code": area["province_code"],
                "population_density": density_by_pc4.get(pc4, ""),
                "leefbaarometer_score": lb.get(pc4, {}).get("score", ""),
                "leefbaarometer_band": lb.get(pc4, {}).get("band", ""),
                "flood_probability_class": klimaat.get(pc4, {}).get(
                    "flood_probability_class", ""
                ),
                "heat_stress_class": klimaat.get(pc4, {}).get("heat_stress_class", ""),
                "road_noise_class": klimaat.get(pc4, {}).get("road_noise_class", ""),
                "incidents_per_1000": politie.get(pc4, {}).get("incidents_per_1000", ""),
            }
        )
    return write_csv(
        curated_root / "postcode4_overview.csv",
        rows,
        columns=(
            "postcode4",
            "municipality_code",
            "province_code",
            "population_density",
            "leefbaarometer_score",
            "leefbaarometer_band",
            "flood_probability_class",
            "heat_stress_class",
            "road_noise_class",
            "incidents_per_1000",
        ),
    )


__all__ = ["build_area_rollups"]
