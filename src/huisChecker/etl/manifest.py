"""Source manifest: versioning and update metadata for every ingestion.

Each source writes a manifest after a successful load. Manifests are
the record of `what data is currently in `data/curated/` and when`. The
report layer reads them to surface caveats and reference periods, and
validation reads them to sanity-check staleness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from huisChecker.etl.io import read_json, write_json


@dataclass(frozen=True)
class SourceManifest:
    source_key: str
    label: str
    provider: str
    mode: str  # "fixture" | "live"
    reference_period: str | None
    retrieved_at: str
    rows_ingested: int
    outputs: tuple[str, ...]
    caveats: tuple[str, ...]
    licence: str | None = None
    notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self)}


def manifest_path(manifests_root: Path, source_key: str) -> Path:
    return manifests_root / f"{source_key}.json"


def write_manifest(manifests_root: Path, manifest: SourceManifest) -> Path:
    return write_json(manifest_path(manifests_root, manifest.source_key), manifest.to_dict())


def read_manifest(manifests_root: Path, source_key: str) -> SourceManifest | None:
    path = manifest_path(manifests_root, source_key)
    if not path.exists():
        return None
    payload = read_json(path)
    return SourceManifest(
        source_key=payload["source_key"],
        label=payload["label"],
        provider=payload["provider"],
        mode=payload["mode"],
        reference_period=payload.get("reference_period"),
        retrieved_at=payload["retrieved_at"],
        rows_ingested=int(payload["rows_ingested"]),
        outputs=tuple(payload.get("outputs", ())),
        caveats=tuple(payload.get("caveats", ())),
        licence=payload.get("licence"),
        notes=payload.get("notes"),
        extra=dict(payload.get("extra", {})),
    )


def now_iso() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "SourceManifest",
    "manifest_path",
    "now_iso",
    "read_manifest",
    "write_manifest",
]
