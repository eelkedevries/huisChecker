"""Leefbaarometer ETL: source-native scores per postcode4.

Produces:
  - data/curated/leefbaarometer_pc4.csv
  - data/curated/layers/leefbaarometer_pc4.geojson  (band-coloured stub)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from huisChecker.contracts import AreaMetricSnapshot, GeographyLevel
from huisChecker.etl.base import ETLJob, ETLResult, SourceMode
from huisChecker.etl.geometry_stubs import pc4_polygon_feature
from huisChecker.etl.io import read_json, write_csv, write_json
from huisChecker.etl.manifest import SourceManifest, now_iso, write_manifest


@dataclass(frozen=True)
class _LbNormalised:
    reference_period: str
    metrics: tuple[AreaMetricSnapshot, ...]
    bands: tuple[tuple[str, str], ...]  # (postcode4, band)


class LeefbaarometerJob(ETLJob):
    source_key = "leefbaarometer"
    label = "Leefbaarometer 3.0"
    caveat = "Samengestelde score gepubliceerd door Leefbaarometer; getoond zoals gepubliceerd."

    def extract(self) -> dict[str, Any]:
        if self.ctx.mode is SourceMode.FIXTURE:
            return read_json(self.ctx.fixtures_root / "leefbaarometer.json")
        raise NotImplementedError("Leefbaarometer live extraction not implemented in MVP.")

    def normalise(self, raw: dict[str, Any]) -> _LbNormalised:
        period = raw["reference_period"]
        now = datetime.now(tz=UTC)
        metrics = tuple(
            AreaMetricSnapshot(
                metric_key="leefbaarometer_score",
                geography_level=GeographyLevel.POSTCODE4.value,
                geography_code=row["postcode4"],
                value=Decimal(str(row["score"])),
                unit=None,
                reference_period=period,
                source_dataset_key=self.source_key,
                computed_at=now,
            )
            for row in raw["pc4_scores"]
        )
        bands = tuple((row["postcode4"], row["band"]) for row in raw["pc4_scores"])
        return _LbNormalised(reference_period=period, metrics=metrics, bands=bands)

    def load(self, n: _LbNormalised) -> ETLResult:
        curated = self.ctx.curated_root
        outputs: list = []
        outputs.append(
            write_csv(
                curated / "leefbaarometer_pc4.csv",
                [
                    {
                        "postcode4": m.geography_code,
                        "score": m.value,
                        "band": dict(n.bands).get(m.geography_code, ""),
                        "reference_period": m.reference_period,
                        "source_dataset_key": m.source_dataset_key,
                    }
                    for m in n.metrics
                ],
                columns=(
                    "postcode4",
                    "score",
                    "band",
                    "reference_period",
                    "source_dataset_key",
                ),
            )
        )
        score_by_pc4 = {m.geography_code: m.value for m in n.metrics}
        layer = {
            "type": "FeatureCollection",
            "features": [
                pc4_polygon_feature(
                    pc4,
                    {
                        "postcode4": pc4,
                        "band": band,
                        "leefbaarometer_score": float(score_by_pc4[pc4])
                        if pc4 in score_by_pc4
                        else None,
                    },
                )
                for pc4, band in n.bands
            ],
        }
        outputs.append(write_json(curated / "layers" / "leefbaarometer_pc4.geojson", layer))
        write_manifest(
            self.ctx.manifests_root,
            SourceManifest(
                source_key=self.source_key,
                label=self.label,
                provider="Ministerie van BZK",
                mode=self.ctx.mode.value,
                reference_period=n.reference_period,
                retrieved_at=now_iso(),
                rows_ingested=len(n.metrics),
                outputs=tuple(str(p.relative_to(self.ctx.data_root)) for p in outputs),
                caveats=(self.caveat,),
                licence="CC-BY",
            ),
        )
        return ETLResult(
            source_key=self.source_key,
            rows_ingested=len(n.metrics),
            outputs=tuple(outputs),
            caveats=(self.caveat,),
            reference_period=n.reference_period,
        )


__all__ = ["LeefbaarometerJob"]
