"""CLI entry point for ETL commands: `python -m huisChecker.etl.cli <cmd>`.

Commands:
  import      full import using fixtures (MVP) or live when wired
  refresh     same as import today, placeholder for delta semantics later
  validate    run validation against the current curated outputs
  smoke       fixture-mode import + validation; used by `make etl-smoke`
"""

from __future__ import annotations

import argparse
import sys

from huisChecker.etl.base import JobContext, SourceMode
from huisChecker.etl.pipeline import import_all, refresh, run_smoke, validate_all


def _print_pipeline(result) -> int:
    for job in result.jobs:
        print(
            f"[{job.status.value:>9}] {job.source_dataset_key:<24} "
            f"rows={job.rows_ingested} period={job.reference_period}"
            + (f"  error={job.error}" if job.error else "")
        )
    if result.rollup_path is not None:
        print(f"rollup: {result.rollup_path}")
    _print_validation(result.validation)
    return 0 if result.ok else 1


def _print_validation(report) -> None:
    for issue in report.issues:
        print(
            f"[{issue.severity:>7}] {issue.check:<12} "
            f"{(issue.source_key or '-'):<22} {issue.path} :: {issue.message}"
        )
    if report.ok:
        print("validation: ok")
    else:
        print(f"validation: FAILED ({len(report.errors())} error(s))")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="huisChecker-etl")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_import = sub.add_parser("import", help="Run full import (fixture mode by default)")
    p_import.add_argument(
        "--live",
        action="store_true",
        help="Use live source endpoints (not implemented in MVP)",
    )
    sub.add_parser("refresh", help="Refresh curated outputs")
    sub.add_parser("validate", help="Validate curated outputs on disk")
    sub.add_parser("smoke", help="Fixture-mode import + validation")
    args = parser.parse_args(argv)

    if args.cmd == "smoke":
        return _print_pipeline(run_smoke())
    if args.cmd == "validate":
        report = validate_all()
        _print_validation(report)
        return 0 if report.ok else 1
    if args.cmd == "refresh":
        return _print_pipeline(refresh())
    if args.cmd == "import":
        mode = SourceMode.LIVE if getattr(args, "live", False) else SourceMode.FIXTURE
        ctx = JobContext.default(mode=mode)
        return _print_pipeline(import_all(ctx))
    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
