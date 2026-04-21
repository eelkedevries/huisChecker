"""Orchestrator for the five MVP source ETL jobs.

Three public entry points map directly to Makefile targets:
  - import_all(ctx)    : run every source job end-to-end
  - refresh(ctx)       : same as import_all but retains prior manifests
                         if a source fails, so partial refreshes stay usable
  - validate_all(ctx)  : schema / uniqueness / join / range / geometry
                         checks against what is currently on disk

`run_smoke` wires everything together with `SourceMode.FIXTURE` so the
pipeline can run offline in tests and CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from huisChecker.contracts import ImportJob
from huisChecker.etl.base import ETLJob, ETLResult, JobContext, SourceMode
from huisChecker.etl.curated.builders import build_area_rollups
from huisChecker.etl.sources import (
    BagJob,
    CbsJob,
    KlimaatJob,
    LeefbaarometerJob,
    PolitieJob,
)
from huisChecker.etl.validation import (
    ValidationIssue,
    ValidationReport,
    check_geojson,
    check_joins,
    check_non_null,
    check_numeric_range,
    check_schema,
    check_unique_key,
)

# Ordered: CBS first so population is available for Politie rate calc.
JOB_CLASSES: tuple[type[ETLJob], ...] = (
    CbsJob,
    BagJob,
    LeefbaarometerJob,
    PolitieJob,
    KlimaatJob,
)


@dataclass(frozen=True)
class PipelineResult:
    jobs: tuple[ImportJob, ...]
    results: tuple[ETLResult, ...]
    rollup_path: Path | None
    validation: ValidationReport

    @property
    def ok(self) -> bool:
        return all(j.status.value == "succeeded" for j in self.jobs) and self.validation.ok


def _run_jobs(
    ctx: JobContext,
    classes: Iterable[type[ETLJob]],
) -> tuple[tuple[ImportJob, ...], tuple[ETLResult, ...]]:
    ctx.curated_root.mkdir(parents=True, exist_ok=True)
    (ctx.curated_root / "layers").mkdir(parents=True, exist_ok=True)
    ctx.manifests_root.mkdir(parents=True, exist_ok=True)
    jobs: list[ImportJob] = []
    results: list[ETLResult] = []
    for cls in classes:
        job = cls(ctx)
        record, result = job.run()
        jobs.append(record)
        if result is not None:
            results.append(result)
    return tuple(jobs), tuple(results)


def import_all(ctx: JobContext | None = None) -> PipelineResult:
    ctx = ctx or JobContext.default(SourceMode.FIXTURE)
    jobs, results = _run_jobs(ctx, JOB_CLASSES)
    rollup = None
    if all(j.status.value == "succeeded" for j in jobs):
        rollup = build_area_rollups(ctx.curated_root)
    report = validate_all(ctx)
    return PipelineResult(jobs=jobs, results=results, rollup_path=rollup, validation=report)


def refresh(ctx: JobContext | None = None) -> PipelineResult:
    # For the MVP, `refresh` is semantically identical to `import_all`
    # but keeps the distinction so the Makefile target stays intention-
    # revealing and future deltas can plug in here without changing
    # callers.
    return import_all(ctx)


def run_smoke(ctx: JobContext | None = None) -> PipelineResult:
    ctx = ctx or JobContext.default(SourceMode.FIXTURE)
    if ctx.mode is not SourceMode.FIXTURE:
        raise ValueError("run_smoke requires SourceMode.FIXTURE")
    return import_all(ctx)


def validate_all(ctx: JobContext | None = None) -> ValidationReport:
    ctx = ctx or JobContext.default()
    curated = ctx.curated_root
    issues: list[ValidationIssue] = []

    issues += check_schema(
        curated / "provinces.csv", ("code", "name"), source_key="cbs_kerncijfers_pc4"
    )
    issues += check_unique_key(curated / "provinces.csv", "code", source_key="cbs_kerncijfers_pc4")
    issues += check_non_null(
        curated / "provinces.csv", ("code", "name"), source_key="cbs_kerncijfers_pc4"
    )

    issues += check_schema(
        curated / "municipalities.csv",
        ("code", "name", "province_code"),
        source_key="cbs_kerncijfers_pc4",
    )
    issues += check_unique_key(
        curated / "municipalities.csv", "code", source_key="cbs_kerncijfers_pc4"
    )
    issues += check_joins(
        curated / "municipalities.csv",
        "province_code",
        curated / "provinces.csv",
        "code",
        source_key="cbs_kerncijfers_pc4",
    )

    issues += check_schema(
        curated / "postcode4_areas.csv",
        ("code", "municipality_code", "province_code"),
        source_key="cbs_kerncijfers_pc4",
    )
    issues += check_unique_key(
        curated / "postcode4_areas.csv", "code", source_key="cbs_kerncijfers_pc4"
    )
    issues += check_joins(
        curated / "postcode4_areas.csv",
        "municipality_code",
        curated / "municipalities.csv",
        "code",
        source_key="cbs_kerncijfers_pc4",
    )

    issues += check_schema(
        curated / "postcode4_metrics.csv",
        (
            "metric_key",
            "geography_level",
            "geography_code",
            "value",
            "reference_period",
            "source_dataset_key",
        ),
        source_key="cbs_kerncijfers_pc4",
    )

    issues += check_schema(
        curated / "addresses.csv",
        ("id", "postcode", "house_number", "postcode4", "municipality_code"),
        source_key="bag",
    )
    issues += check_unique_key(curated / "addresses.csv", "id", source_key="bag")
    issues += check_joins(
        curated / "addresses.csv",
        "postcode4",
        curated / "postcode4_areas.csv",
        "code",
        source_key="bag",
    )
    issues += check_non_null(
        curated / "addresses.csv",
        ("id", "postcode", "street", "city", "postcode4"),
        source_key="bag",
    )

    issues += check_schema(
        curated / "bag_objects.csv",
        ("id", "construction_year"),
        source_key="bag",
    )
    issues += check_unique_key(curated / "bag_objects.csv", "id", source_key="bag")
    issues += check_numeric_range(
        curated / "bag_objects.csv",
        "construction_year",
        min_value=1000,
        max_value=2100,
        source_key="bag",
    )

    issues += check_schema(
        curated / "leefbaarometer_pc4.csv",
        ("postcode4", "score", "band"),
        source_key="leefbaarometer",
    )
    issues += check_numeric_range(
        curated / "leefbaarometer_pc4.csv",
        "score",
        min_value=0,
        max_value=10,
        source_key="leefbaarometer",
    )

    issues += check_schema(
        curated / "politie_pc4_incidents.csv",
        ("postcode4", "total_incidents", "incidents_per_1000"),
        source_key="politie_opendata",
    )
    issues += check_numeric_range(
        curated / "politie_pc4_incidents.csv",
        "incidents_per_1000",
        min_value=0,
        source_key="politie_opendata",
    )
    issues += check_joins(
        curated / "politie_pc4_incidents.csv",
        "postcode4",
        curated / "postcode4_areas.csv",
        "code",
        source_key="politie_opendata",
    )

    issues += check_schema(
        curated / "klimaat_pc4.csv",
        ("postcode4", "flood_probability_class"),
        source_key="klimaateffectatlas",
    )

    issues += check_geojson(
        curated / "layers" / "bag_footprints.geojson", source_key="bag"
    )
    issues += check_geojson(
        curated / "layers" / "klimaateffect_flood.geojson", source_key="klimaateffectatlas"
    )
    issues += check_geojson(
        curated / "layers" / "leefbaarometer_pc4.geojson", source_key="leefbaarometer"
    )
    issues += check_geojson(
        curated / "layers" / "cbs_population_density_pc4.geojson",
        source_key="cbs_kerncijfers_pc4",
    )

    return ValidationReport(issues=tuple(issues))


__all__ = [
    "JOB_CLASSES",
    "PipelineResult",
    "import_all",
    "refresh",
    "run_smoke",
    "validate_all",
]
