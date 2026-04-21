"""ETL pipeline tests.

These drive the pipeline with bundled fixtures (offline) and assert:
- every source job succeeds
- curated outputs exist on disk with expected schema
- validation returns a clean report
- rollup joins cleanly across sources
"""

from __future__ import annotations

from pathlib import Path

import pytest

from huisChecker.etl import run_smoke
from huisChecker.etl.base import JobContext, SourceMode
from huisChecker.etl.io import read_csv, read_json
from huisChecker.etl.manifest import read_manifest
from huisChecker.etl.pipeline import import_all, validate_all
from huisChecker.etl.sources import CORE_SOURCES, source_registry


@pytest.fixture
def tmp_ctx(tmp_path: Path) -> JobContext:
    data_root = tmp_path / "data"
    fixtures = Path(__file__).resolve().parents[1] / "src/huisChecker/etl/fixtures"
    return JobContext(
        data_root=data_root,
        curated_root=data_root / "curated",
        manifests_root=data_root / "manifests",
        fixtures_root=fixtures,
        mode=SourceMode.FIXTURE,
    )


def test_source_registry_covers_all_five_mvp_groups() -> None:
    keys = set(source_registry.keys())
    assert {
        "cbs_kerncijfers_pc4",
        "bag",
        "leefbaarometer",
        "politie_opendata",
        "klimaateffectatlas",
    } <= keys
    # Registry must not silently pick up deferred sources.
    for s in CORE_SOURCES:
        assert s.key in keys


def test_smoke_pipeline_produces_curated_outputs(tmp_ctx: JobContext) -> None:
    result = run_smoke(tmp_ctx)

    assert all(j.status.value == "succeeded" for j in result.jobs), [
        (j.source_dataset_key, j.error) for j in result.jobs if j.error
    ]
    curated = tmp_ctx.curated_root
    for relative in (
        "provinces.csv",
        "municipalities.csv",
        "postcode4_areas.csv",
        "postcode4_metrics.csv",
        "municipality_metrics.csv",
        "province_metrics.csv",
        "addresses.csv",
        "bag_objects.csv",
        "leefbaarometer_pc4.csv",
        "politie_pc4_incidents.csv",
        "klimaat_pc4.csv",
        "postcode4_overview.csv",
    ):
        assert (curated / relative).exists(), f"missing curated output: {relative}"

    for layer in (
        "bag_footprints.geojson",
        "leefbaarometer_pc4.geojson",
        "klimaateffect_flood.geojson",
    ):
        assert (curated / "layers" / layer).exists()


def test_smoke_validation_clean(tmp_ctx: JobContext) -> None:
    result = run_smoke(tmp_ctx)
    errors = result.validation.errors()
    assert not errors, [
        (e.check, e.source_key, e.path, e.message) for e in errors
    ]


def test_manifests_written_for_each_source(tmp_ctx: JobContext) -> None:
    run_smoke(tmp_ctx)
    for key in (
        "cbs_kerncijfers_pc4",
        "bag",
        "leefbaarometer",
        "politie_opendata",
        "klimaateffectatlas",
    ):
        manifest = read_manifest(tmp_ctx.manifests_root, key)
        assert manifest is not None, f"missing manifest for {key}"
        assert manifest.rows_ingested > 0
        assert manifest.reference_period
        assert manifest.caveats
        assert manifest.mode == SourceMode.FIXTURE.value


def test_import_all_is_idempotent(tmp_ctx: JobContext) -> None:
    first = import_all(tmp_ctx)
    second = import_all(tmp_ctx)
    assert first.ok and second.ok
    # Row counts for source jobs should match across runs.
    by_source_first = {r.source_key: r.rows_ingested for r in first.results}
    by_source_second = {r.source_key: r.rows_ingested for r in second.results}
    assert by_source_first == by_source_second


def test_politie_rate_non_negative(tmp_ctx: JobContext) -> None:
    run_smoke(tmp_ctx)
    rows = read_csv(tmp_ctx.curated_root / "politie_pc4_incidents.csv")
    assert rows
    for row in rows:
        assert float(row["incidents_per_1000"]) >= 0


def test_overview_rollup_covers_all_pc4(tmp_ctx: JobContext) -> None:
    run_smoke(tmp_ctx)
    areas_path = tmp_ctx.curated_root / "postcode4_areas.csv"
    overview_path = tmp_ctx.curated_root / "postcode4_overview.csv"
    areas = {row["code"] for row in read_csv(areas_path)}
    overview = {row["postcode4"] for row in read_csv(overview_path)}
    assert areas == overview


def test_geojson_layers_are_feature_collections(tmp_ctx: JobContext) -> None:
    run_smoke(tmp_ctx)
    names = (
        "bag_footprints.geojson",
        "leefbaarometer_pc4.geojson",
        "klimaateffect_flood.geojson",
    )
    for name in names:
        payload = read_json(tmp_ctx.curated_root / "layers" / name)
        assert payload["type"] == "FeatureCollection"
        assert isinstance(payload.get("features"), list)


def test_validate_all_catches_missing_curated(tmp_path: Path) -> None:
    empty_ctx = JobContext(
        data_root=tmp_path / "data",
        curated_root=tmp_path / "data/curated",
        manifests_root=tmp_path / "data/manifests",
        fixtures_root=Path(__file__).resolve().parents[1] / "src/huisChecker/etl/fixtures",
        mode=SourceMode.FIXTURE,
    )
    report = validate_all(empty_ctx)
    assert not report.ok
    assert any(issue.check == "schema" for issue in report.errors())


def test_source_mode_live_raises_not_implemented(tmp_ctx: JobContext) -> None:
    from huisChecker.etl.base import JobContext as JC
    live_ctx = JC(
        data_root=tmp_ctx.data_root,
        curated_root=tmp_ctx.curated_root,
        manifests_root=tmp_ctx.manifests_root,
        fixtures_root=tmp_ctx.fixtures_root,
        mode=SourceMode.LIVE,
    )
    result = import_all(live_ctx)
    # Every job should have recorded a failure, not silently succeeded.
    assert all(j.status.value == "failed" for j in result.jobs)
