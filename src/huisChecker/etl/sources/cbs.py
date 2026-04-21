"""CBS postcode and regional statistics ETL.

Produces curated tables:
  - data/curated/provinces.csv
  - data/curated/municipalities.csv
  - data/curated/postcode4_areas.csv
  - data/curated/postcode4_metrics.csv
  - data/curated/municipality_metrics.csv
  - data/curated/province_metrics.csv

In `live` mode this is the place to call CBS StatLine / CBS open-data
endpoints. The MVP ships only the `fixture` code path so the pipeline
can run offline; switching to live is a later prompt's concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from huisChecker.contracts import (
    AreaMetricSnapshot,
    GeographyLevel,
    Municipality,
    Postcode4Area,
    Province,
)
from huisChecker.etl.base import ETLJob, ETLResult, SourceMode
from huisChecker.etl.io import read_json, write_csv
from huisChecker.etl.manifest import SourceManifest, now_iso, write_manifest


@dataclass(frozen=True)
class _CbsNormalised:
    reference_period: str
    provinces: tuple[Province, ...]
    municipalities: tuple[Municipality, ...]
    postcode4_areas: tuple[Postcode4Area, ...]
    pc4_metrics: tuple[AreaMetricSnapshot, ...]
    municipality_metrics: tuple[AreaMetricSnapshot, ...]
    province_metrics: tuple[AreaMetricSnapshot, ...]


class CbsJob(ETLJob):
    source_key = "cbs_kerncijfers_pc4"
    label = "CBS kerncijfers per postcode 4"
    caveat = "CBS PC4 snapshot; values are area averages, not address-level."

    def extract(self) -> dict[str, Any]:
        if self.ctx.mode is SourceMode.FIXTURE:
            return read_json(self.ctx.fixtures_root / "cbs_pc4.json")
        raise NotImplementedError(
            "CBS live extraction is not implemented in the MVP. "
            "Run with mode=fixture or wire CBS StatLine access in a later prompt."
        )

    def normalise(self, raw: dict[str, Any]) -> _CbsNormalised:
        period = raw["reference_period"]
        now = datetime.now(tz=UTC)
        provinces = tuple(
            Province(code=row["code"], name=row["name"]) for row in raw["provinces"]
        )
        municipalities = tuple(
            Municipality(
                code=row["code"],
                name=row["name"],
                province_code=row["province_code"],
            )
            for row in raw["municipalities"]
        )
        pc4_areas = tuple(
            Postcode4Area(
                code=row["code"],
                municipality_code=row["municipality_code"],
                province_code=row["province_code"],
            )
            for row in raw["postcode4_areas"]
        )
        pc4_metrics = tuple(
            AreaMetricSnapshot(
                metric_key="cbs_population_density",
                geography_level=GeographyLevel.POSTCODE4.value,
                geography_code=row["postcode4"],
                value=Decimal(str(row["population_density"])),
                unit="inhabitants/km2",
                reference_period=period,
                source_dataset_key=self.source_key,
                computed_at=now,
            )
            for row in raw["pc4_metrics"]
        )
        municipality_metrics = tuple(
            AreaMetricSnapshot(
                metric_key="cbs_population",
                geography_level=GeographyLevel.MUNICIPALITY.value,
                geography_code=row["municipality_code"],
                value=Decimal(str(row["population"])),
                unit="inhabitants",
                reference_period=period,
                source_dataset_key=self.source_key,
                computed_at=now,
            )
            for row in raw["municipality_metrics"]
        )
        province_metrics = tuple(
            AreaMetricSnapshot(
                metric_key="cbs_population",
                geography_level=GeographyLevel.PROVINCE.value,
                geography_code=row["province_code"],
                value=Decimal(str(row["population"])),
                unit="inhabitants",
                reference_period=period,
                source_dataset_key=self.source_key,
                computed_at=now,
            )
            for row in raw["province_metrics"]
        )
        return _CbsNormalised(
            reference_period=period,
            provinces=provinces,
            municipalities=municipalities,
            postcode4_areas=pc4_areas,
            pc4_metrics=pc4_metrics,
            municipality_metrics=municipality_metrics,
            province_metrics=province_metrics,
        )

    def load(self, n: _CbsNormalised) -> ETLResult:
        curated = self.ctx.curated_root
        outputs: list = []
        outputs.append(
            write_csv(
                curated / "provinces.csv",
                [p.model_dump() for p in n.provinces],
                columns=("code", "name"),
            )
        )
        outputs.append(
            write_csv(
                curated / "municipalities.csv",
                [m.model_dump() for m in n.municipalities],
                columns=("code", "name", "province_code"),
            )
        )
        outputs.append(
            write_csv(
                curated / "postcode4_areas.csv",
                [a.model_dump() for a in n.postcode4_areas],
                columns=("code", "municipality_code", "province_code", "geometry_ref"),
            )
        )
        outputs.append(
            write_csv(
                curated / "postcode4_metrics.csv",
                [m.model_dump() for m in n.pc4_metrics],
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
        )
        outputs.append(
            write_csv(
                curated / "municipality_metrics.csv",
                [m.model_dump() for m in n.municipality_metrics],
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
        )
        outputs.append(
            write_csv(
                curated / "province_metrics.csv",
                [m.model_dump() for m in n.province_metrics],
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
        )
        rows = (
            len(n.provinces)
            + len(n.municipalities)
            + len(n.postcode4_areas)
            + len(n.pc4_metrics)
            + len(n.municipality_metrics)
            + len(n.province_metrics)
        )
        write_manifest(
            self.ctx.manifests_root,
            SourceManifest(
                source_key=self.source_key,
                label=self.label,
                provider="CBS",
                mode=self.ctx.mode.value,
                reference_period=n.reference_period,
                retrieved_at=now_iso(),
                rows_ingested=rows,
                outputs=tuple(str(p.relative_to(self.ctx.data_root)) for p in outputs),
                caveats=(self.caveat,),
                licence="CBS-open-data",
            ),
        )
        return ETLResult(
            source_key=self.source_key,
            rows_ingested=rows,
            outputs=tuple(outputs),
            caveats=(self.caveat,),
            reference_period=n.reference_period,
        )

__all__ = ["CbsJob"]
