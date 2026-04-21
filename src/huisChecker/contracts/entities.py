"""Core persisted entities for huisChecker.

These Pydantic models are the shared vocabulary used by ETL, report
assembly, UI rendering, and payment flows. They intentionally stay
framework-agnostic: no ORM coupling, no request/response shapes.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from huisChecker.contracts.identifiers import (
    BagObjectId,
    MunicipalityCode,
    NummeraanduidingId,
    Postcode,
    Postcode4,
    ProvinceCode,
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Province(_Frozen):
    code: ProvinceCode
    name: str


class Municipality(_Frozen):
    code: MunicipalityCode
    name: str
    province_code: ProvinceCode


class Postcode4Area(_Frozen):
    code: Postcode4
    municipality_code: MunicipalityCode
    province_code: ProvinceCode
    # Geometry handled out-of-band (vector tiles); keep a stable feature ref.
    geometry_ref: str | None = None


class BagObject(_Frozen):
    """BAG `verblijfsobject` — the building unit for an address."""

    id: BagObjectId
    construction_year: int | None = None
    use_purpose: tuple[str, ...] = ()
    surface_area_m2: int | None = None
    latitude: float | None = None
    longitude: float | None = None


class Address(_Frozen):
    id: str  # canonical_address_id(...)
    postcode: Postcode
    house_number: int
    house_number_addition: str | None = None
    street: str
    city: str
    nummeraanduiding_id: NummeraanduidingId | None = None
    bag_object_id: BagObjectId | None = None
    postcode4: Postcode4
    municipality_code: MunicipalityCode
    province_code: ProvinceCode


class SourceDataset(_Frozen):
    """Registry entry describing an external dataset."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    provider: str
    url: HttpUrl | None = None
    refresh_cadence: str  # e.g. "annual", "quarterly", "ad hoc"
    coverage: str  # e.g. "NL, postcode4"
    licence: str | None = None
    notes: str | None = None


class AreaMetricSnapshot(_Frozen):
    """A precomputed metric value for a given area and period."""

    metric_key: str
    geography_level: str  # GeographyLevel value (kept as str to avoid cycles)
    geography_code: str
    value: Decimal | None
    unit: str | None
    reference_period: str  # ISO year or "YYYY-YYYY"
    source_dataset_key: str
    computed_at: datetime


class ReportStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class ReportModuleStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class ReportModuleResult(_Frozen):
    """Runtime output of a single report module for one address."""

    module_key: str
    status: ReportModuleStatus
    summary: str
    findings: tuple["ReportFindingPayload", ...] = ()
    caveats: tuple[str, ...] = ()
    data_points: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime


class ReportFindingPayload(_Frozen):
    """Single comparable measurement rendered in a report section."""

    metric_key: str
    label: str
    value: Decimal | None
    unit: str | None
    comparison_mode: str
    comparison_value: Decimal | None = None
    comparison_label: str | None = None
    caveat: str | None = None


class Report(_Frozen):
    id: str
    address_id: str
    created_at: datetime
    status: ReportStatus
    modules: tuple[ReportModuleResult, ...] = ()


class ReportAccessLink(_Frozen):
    token: str
    report_id: str
    created_at: datetime
    expires_at: datetime
    revoked: bool = False


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(_Frozen):
    id: str
    report_id: str
    provider: str  # e.g. "mollie", "stripe"
    provider_reference: str | None
    amount_cents: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    status: PaymentStatus
    created_at: datetime
    paid_at: datetime | None = None


class ImportJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ImportJob(_Frozen):
    id: str
    source_dataset_key: str
    status: ImportJobStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    reference_period: str | None = None
    rows_ingested: int | None = None
    error: str | None = None
    scheduled_for: date | None = None


__all__ = [
    "Address",
    "AreaMetricSnapshot",
    "BagObject",
    "ImportJob",
    "ImportJobStatus",
    "Municipality",
    "Payment",
    "PaymentStatus",
    "Postcode4Area",
    "Province",
    "Report",
    "ReportAccessLink",
    "ReportFindingPayload",
    "ReportModuleResult",
    "ReportModuleStatus",
    "ReportStatus",
    "SourceDataset",
]
