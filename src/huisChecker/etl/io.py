"""Small I/O helpers for curated CSV and JSON outputs.

Kept stdlib-only to avoid pulling pyarrow/pandas for the MVP. Curated
tables are small (5 source groups, tens to hundreds of rows in MVP
slices) so CSV is adequate.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], *, columns: Sequence[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({c: _serialise(row.get(c)) for c in columns})
    return path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    return path


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _serialise(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def distinct(values: Iterable[Any]) -> list[Any]:
    seen: list[Any] = []
    marker: set[Any] = set()
    for v in values:
        if v in marker:
            continue
        marker.add(v)
        seen.append(v)
    return seen


__all__ = [
    "distinct",
    "read_csv",
    "read_json",
    "write_csv",
    "write_json",
]
