"""Core ETL primitives: job base class, result record, execution context.

`ETLJob` is deliberately minimal. Each source module subclasses it and
implements `extract` / `normalise` / `load`. The base class owns:
  - run orchestration (extract -> normalise -> load -> manifest)
  - ImportJob bookkeeping
  - error capture

No network I/O lives here. Sources decide how to fetch; when the job
runs in smoke mode they must read from `fixtures/` instead of the
network so tests stay offline and deterministic.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from huisChecker.contracts import ImportJob, ImportJobStatus


class SourceMode(StrEnum):
    """Where a job should read its raw data from."""

    FIXTURE = "fixture"  # bundled tiny sample; used by smoke tests
    LIVE = "live"  # real external endpoint; used by `import` / `refresh`


@dataclass(frozen=True)
class JobContext:
    """Paths and mode handed to every ETL job at run time."""

    data_root: Path
    curated_root: Path
    manifests_root: Path
    fixtures_root: Path
    mode: SourceMode = SourceMode.FIXTURE
    reference_period: str | None = None

    @classmethod
    def default(cls, mode: SourceMode = SourceMode.FIXTURE) -> "JobContext":
        project_root = Path(__file__).resolve().parents[3]
        data_root = project_root / "data"
        return cls(
            data_root=data_root,
            curated_root=data_root / "curated",
            manifests_root=data_root / "manifests",
            fixtures_root=Path(__file__).resolve().parent / "fixtures",
            mode=mode,
        )


@dataclass
class ETLResult:
    """Outcome of a single ETL job run."""

    source_key: str
    rows_ingested: int
    outputs: tuple[Path, ...] = ()
    caveats: tuple[str, ...] = ()
    reference_period: str | None = None
    artefacts: dict[str, Any] = field(default_factory=dict)


class ETLJob(ABC):
    """Base class for one source-group ETL.

    Subclass lifecycle:
      extract  -> returns raw payload (dict/list, source-shaped)
      normalise -> converts raw payload to Pydantic-typed rows
      load     -> writes curated CSV/JSON outputs, returns ETLResult
    """

    source_key: str
    label: str
    caveat: str

    def __init__(self, ctx: JobContext) -> None:
        self.ctx = ctx

    # --- lifecycle hooks -------------------------------------------------
    @abstractmethod
    def extract(self) -> Any: ...

    @abstractmethod
    def normalise(self, raw: Any) -> Any: ...

    @abstractmethod
    def load(self, normalised: Any) -> ETLResult: ...

    # --- orchestration ---------------------------------------------------
    def run(self) -> tuple[ImportJob, ETLResult | None]:
        started = datetime.now(tz=UTC)
        stamp = started.strftime("%Y%m%dT%H%M%SZ")
        job_id = f"job_{self.source_key}_{stamp}_{uuid.uuid4().hex[:6]}"
        try:
            raw = self.extract()
            normalised = self.normalise(raw)
            result = self.load(normalised)
        except Exception as exc:  # pragma: no cover - error path exercised in tests
            finished = datetime.now(tz=UTC)
            return (
                ImportJob(
                    id=job_id,
                    source_dataset_key=self.source_key,
                    status=ImportJobStatus.FAILED,
                    started_at=started,
                    finished_at=finished,
                    reference_period=self.ctx.reference_period,
                    rows_ingested=None,
                    error=f"{type(exc).__name__}: {exc}",
                ),
                None,
            )
        finished = datetime.now(tz=UTC)
        return (
            ImportJob(
                id=job_id,
                source_dataset_key=self.source_key,
                status=ImportJobStatus.SUCCEEDED,
                started_at=started,
                finished_at=finished,
                reference_period=result.reference_period or self.ctx.reference_period,
                rows_ingested=result.rows_ingested,
                error=None,
            ),
            result,
        )


__all__ = [
    "ETLJob",
    "ETLResult",
    "JobContext",
    "SourceMode",
]
