"""Post-load validation checks for curated outputs.

All checks operate on the CSV/JSON artefacts written by source jobs so
they exercise what the app will actually read. Failure surfaces as
`ValidationIssue` entries, never exceptions, to keep the pipeline
CLI-friendly; `validate_all` returns non-zero-exit info instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from huisChecker.etl.io import read_csv


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # "error" | "warning"
    check: str
    source_key: str | None
    path: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")


def _err(check: str, path: Path, message: str, source_key: str | None = None) -> ValidationIssue:
    return ValidationIssue("error", check, source_key, str(path), message)


def _warn(check: str, path: Path, message: str, source_key: str | None = None) -> ValidationIssue:
    return ValidationIssue("warning", check, source_key, str(path), message)


def check_schema(
    path: Path, required: Iterable[str], source_key: str | None = None
) -> list[ValidationIssue]:
    if not path.exists():
        return [_err("schema", path, "curated file missing", source_key)]
    rows = read_csv(path)
    if not rows:
        return [_warn("schema", path, "curated file is empty", source_key)]
    missing = [c for c in required if c not in rows[0]]
    if missing:
        return [_err("schema", path, f"missing columns: {missing}", source_key)]
    return []


def check_unique_key(
    path: Path, key: str | tuple[str, ...], source_key: str | None = None
) -> list[ValidationIssue]:
    if not path.exists():
        return []
    rows = read_csv(path)
    keys = key if isinstance(key, tuple) else (key,)
    seen: dict[tuple[str, ...], int] = {}
    dups: list[tuple[str, ...]] = []
    for row in rows:
        k = tuple(row.get(c, "") for c in keys)
        seen[k] = seen.get(k, 0) + 1
        if seen[k] == 2:
            dups.append(k)
    if dups:
        sample = ", ".join("|".join(d) for d in dups[:3])
        return [_err("unique_key", path, f"duplicates on {keys}: {sample}", source_key)]
    return []


def check_non_null(
    path: Path, columns: Iterable[str], source_key: str | None = None
) -> list[ValidationIssue]:
    if not path.exists():
        return []
    rows = read_csv(path)
    issues: list[ValidationIssue] = []
    for col in columns:
        bad = [i for i, r in enumerate(rows) if not (r.get(col, "") or "").strip()]
        if bad:
            issues.append(
                _err(
                    "non_null",
                    path,
                    f"column {col!r} empty in rows {bad[:3]} (+{max(0, len(bad) - 3)})",
                    source_key,
                )
            )
    return issues


def check_numeric_range(
    path: Path,
    column: str,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
    source_key: str | None = None,
) -> list[ValidationIssue]:
    if not path.exists():
        return []
    issues: list[ValidationIssue] = []
    rows = read_csv(path)
    for i, row in enumerate(rows):
        raw = (row.get(column, "") or "").strip()
        if not raw:
            continue
        try:
            value = Decimal(raw)
        except InvalidOperation:
            msg = f"row {i} col {column!r} not numeric: {raw!r}"
            issues.append(_err("range", path, msg, source_key))
            continue
        if min_value is not None and value < Decimal(str(min_value)):
            msg = f"row {i} col {column!r} below {min_value}: {value}"
            issues.append(_err("range", path, msg, source_key))
        if max_value is not None and value > Decimal(str(max_value)):
            msg = f"row {i} col {column!r} above {max_value}: {value}"
            issues.append(_err("range", path, msg, source_key))
    return issues


def check_joins(
    child_path: Path,
    child_key: str,
    parent_path: Path,
    parent_key: str,
    *,
    source_key: str | None = None,
) -> list[ValidationIssue]:
    if not (child_path.exists() and parent_path.exists()):
        return []
    parents = {row[parent_key] for row in read_csv(parent_path) if row.get(parent_key)}
    orphans: list[str] = []
    for row in read_csv(child_path):
        value = (row.get(child_key, "") or "").strip()
        if value and value not in parents:
            orphans.append(value)
    if orphans:
        return [
            _err(
                "join",
                child_path,
                f"{len(orphans)} rows missing parent {parent_key} (sample {orphans[:3]})",
                source_key,
            )
        ]
    return []


def check_geojson(path: Path, source_key: str | None = None) -> list[ValidationIssue]:
    if not path.exists():
        return []
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        return [_err("geometry", path, f"invalid JSON: {exc.msg}", source_key)]
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        return [_err("geometry", path, "not a FeatureCollection", source_key)]
    features = payload.get("features", [])
    issues: list[ValidationIssue] = []
    for idx, feature in enumerate(features):
        geom = feature.get("geometry") if isinstance(feature, dict) else None
        if not isinstance(geom, dict) or geom.get("type") not in {
            "Point",
            "LineString",
            "Polygon",
            "MultiPolygon",
            "MultiLineString",
            "MultiPoint",
        }:
            issues.append(_err("geometry", path, f"feature {idx} has invalid geometry", source_key))
            continue
        coords = geom.get("coordinates")
        if coords is None:
            issues.append(_err("geometry", path, f"feature {idx} missing coordinates", source_key))
    return issues


__all__ = [
    "ValidationIssue",
    "ValidationReport",
    "check_geojson",
    "check_joins",
    "check_non_null",
    "check_numeric_range",
    "check_schema",
    "check_unique_key",
]
