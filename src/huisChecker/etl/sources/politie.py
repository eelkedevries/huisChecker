"""Politie open-data ETL: registered incidents, normalised per 1000.

Requires the CBS job to have already written `postcode4_metrics.csv`
(for population density). The pipeline orchestrator guarantees this
ordering.

Produces:
  - data/curated/politie_pc4_incidents.csv  (raw counts + rate)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from huisChecker.contracts import AreaMetricSnapshot, GeographyLevel
from huisChecker.etl.base import ETLJob, ETLResult, SourceMode
from huisChecker.etl.io import read_csv, read_json, write_csv
from huisChecker.etl.manifest import SourceManifest, now_iso, write_manifest


@dataclass(frozen=True)
class _PolitieNormalised:
    reference_period: str
    rate_metrics: tuple[AreaMetricSnapshot, ...]
    totals: dict[str, int]
    populations: dict[str, Decimal]


class PolitieJob(ETLJob):
    source_key = "politie_opendata"
    label = "Politie registered incidents"
    caveat = "Alleen gemelde incidenten; onder-rapportage varieert per type incident."

    def extract(self) -> dict[str, Any]:
        if self.ctx.mode is SourceMode.FIXTURE:
            return read_json(self.ctx.fixtures_root / "politie.json")
        raise NotImplementedError("Politie live extraction not implemented in MVP.")

    def normalise(self, raw: dict[str, Any]) -> _PolitieNormalised:
        period = raw["reference_period"]
        totals = {row["postcode4"]: int(row["total_incidents"]) for row in raw["pc4_incidents"]}
        populations = self._load_populations()
        now = datetime.now(tz=UTC)
        rate_metrics: list[AreaMetricSnapshot] = []
        for pc4, count in totals.items():
            pop = populations.get(pc4)
            if pop is None or pop == 0:
                continue
            rate = (Decimal(count) * Decimal(1000)) / pop
            rate_metrics.append(
                AreaMetricSnapshot(
                    metric_key="politie_registered_incidents_per_1000",
                    geography_level=GeographyLevel.POSTCODE4.value,
                    geography_code=pc4,
                    value=rate.quantize(Decimal("0.01")),
                    unit="incidents/1000",
                    reference_period=period,
                    source_dataset_key=self.source_key,
                    computed_at=now,
                )
            )
        return _PolitieNormalised(
            reference_period=period,
            rate_metrics=tuple(rate_metrics),
            totals=totals,
            populations=populations,
        )

    def _load_populations(self) -> dict[str, Decimal]:
        # Need raw population per PC4; CBS writes density, not population.
        # Read from the CBS fixture directly so the pipeline order
        # requirement is satisfied regardless of curated CSV column set.
        cbs = read_json(self.ctx.fixtures_root / "cbs_pc4.json")
        return {row["postcode4"]: Decimal(str(row["population"])) for row in cbs["pc4_metrics"]}

    def load(self, n: _PolitieNormalised) -> ETLResult:
        curated = self.ctx.curated_root
        rows = [
            {
                "postcode4": m.geography_code,
                "total_incidents": n.totals[m.geography_code],
                "incidents_per_1000": m.value,
                "reference_period": m.reference_period,
                "source_dataset_key": m.source_dataset_key,
            }
            for m in n.rate_metrics
        ]
        path = write_csv(
            curated / "politie_pc4_incidents.csv",
            rows,
            columns=(
                "postcode4",
                "total_incidents",
                "incidents_per_1000",
                "reference_period",
                "source_dataset_key",
            ),
        )
        # Also append rate metrics to postcode4_metrics.csv for the
        # report layer's consumption, without duplicating CBS rows.
        pc4_metrics_path = curated / "postcode4_metrics.csv"
        existing = read_csv(pc4_metrics_path) if pc4_metrics_path.exists() else []
        existing_keys = {
            (r["metric_key"], r["geography_code"], r["reference_period"]) for r in existing
        }
        for m in n.rate_metrics:
            key = (m.metric_key, m.geography_code, m.reference_period)
            if key in existing_keys:
                continue
            existing.append(
                {
                    "metric_key": m.metric_key,
                    "geography_level": m.geography_level,
                    "geography_code": m.geography_code,
                    "value": str(m.value),
                    "unit": m.unit or "",
                    "reference_period": m.reference_period,
                    "source_dataset_key": m.source_dataset_key,
                    "computed_at": m.computed_at.isoformat(),
                }
            )
        write_csv(
            pc4_metrics_path,
            existing,
            columns=(
                "metric_key",
                "geography_level",
                "geography_code",
                "value",
                "unit",
                "reference_period",
                "source_dataset_key",
                "computed_at",
            ),
        )
        write_manifest(
            self.ctx.manifests_root,
            SourceManifest(
                source_key=self.source_key,
                label=self.label,
                provider="Nationale Politie",
                mode=self.ctx.mode.value,
                reference_period=n.reference_period,
                retrieved_at=now_iso(),
                rows_ingested=len(n.rate_metrics),
                outputs=(str(path.relative_to(self.ctx.data_root)),),
                caveats=(self.caveat,),
                licence="CC-BY",
                notes="Rates computed using CBS PC4 population for the same MVP slice.",
            ),
        )
        return ETLResult(
            source_key=self.source_key,
            rows_ingested=len(n.rate_metrics),
            outputs=(path,),
            caveats=(self.caveat,),
            reference_period=n.reference_period,
        )


__all__ = ["PolitieJob"]
