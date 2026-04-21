"""Klimaateffectatlas + selected Atlas Leefomgeving ETL.

Only stable, downloadable/service-backed layers are ingested. The
portal itself is never a runtime dependency. For the MVP we ship:
  - flood probability classes per PC4 (Klimaateffectatlas)
  - heat stress classes per PC4 (Klimaateffectatlas)
  - road-noise classes per PC4 (Atlas Leefomgeving)

Produces:
  - data/curated/klimaat_pc4.csv
  - data/curated/layers/klimaateffect_flood.geojson
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from huisChecker.etl.base import ETLJob, ETLResult, SourceMode
from huisChecker.etl.geometry_stubs import pc4_polygon_feature
from huisChecker.etl.io import read_json, write_csv, write_json
from huisChecker.etl.manifest import SourceManifest, now_iso, write_manifest


@dataclass(frozen=True)
class _KlimaatNormalised:
    reference_period: str
    rows: tuple[dict[str, Any], ...]


class KlimaatJob(ETLJob):
    source_key = "klimaateffectatlas"
    label = "Klimaateffectatlas + Atlas Leefomgeving selection"
    caveat = "Scenario-based modelling; classes, not precise probabilities."

    def extract(self) -> dict[str, Any]:
        if self.ctx.mode is SourceMode.FIXTURE:
            return read_json(self.ctx.fixtures_root / "klimaat.json")
        raise NotImplementedError("Klimaat live extraction not implemented in MVP.")

    def normalise(self, raw: dict[str, Any]) -> _KlimaatNormalised:
        period = raw["reference_period"]
        flood = {row["postcode4"]: row["class"] for row in raw["flood_probability_pc4"]}
        heat = {row["postcode4"]: row["class"] for row in raw["heat_stress_pc4"]}
        noise = {
            row["postcode4"]: row["road_noise_class"]
            for row in raw["atlas_leefomgeving_noise_pc4"]
        }
        keys = sorted(set(flood) | set(heat) | set(noise))
        rows = tuple(
            {
                "postcode4": k,
                "flood_probability_class": flood.get(k, ""),
                "heat_stress_class": heat.get(k, ""),
                "road_noise_class": noise.get(k, ""),
                "reference_period": period,
            }
            for k in keys
        )
        return _KlimaatNormalised(reference_period=period, rows=rows)

    def load(self, n: _KlimaatNormalised) -> ETLResult:
        curated = self.ctx.curated_root
        outputs: list = []
        outputs.append(
            write_csv(
                curated / "klimaat_pc4.csv",
                list(n.rows),
                columns=(
                    "postcode4",
                    "flood_probability_class",
                    "heat_stress_class",
                    "road_noise_class",
                    "reference_period",
                ),
            )
        )
        flood_layer = {
            "type": "FeatureCollection",
            "features": [
                pc4_polygon_feature(
                    row["postcode4"],
                    {
                        "postcode4": row["postcode4"],
                        "class": row["flood_probability_class"],
                    },
                )
                for row in n.rows
                if row["flood_probability_class"]
            ],
        }
        outputs.append(write_json(curated / "layers" / "klimaateffect_flood.geojson", flood_layer))
        write_manifest(
            self.ctx.manifests_root,
            SourceManifest(
                source_key=self.source_key,
                label=self.label,
                provider="Stichting CAS / RIVM",
                mode=self.ctx.mode.value,
                reference_period=n.reference_period,
                retrieved_at=now_iso(),
                rows_ingested=len(n.rows),
                outputs=tuple(str(p.relative_to(self.ctx.data_root)) for p in outputs),
                caveats=(
                    self.caveat,
                    "Atlas Leefomgeving noise layer bundled here as a curated downstream.",
                ),
                licence="Open data",
                notes="Only stable, downloadable layers; portal is not a runtime dependency.",
            ),
        )
        return ETLResult(
            source_key=self.source_key,
            rows_ingested=len(n.rows),
            outputs=tuple(outputs),
            caveats=(self.caveat,),
            reference_period=n.reference_period,
        )


__all__ = ["KlimaatJob"]
