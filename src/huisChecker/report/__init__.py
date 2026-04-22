"""Report generation for address due-diligence."""

from huisChecker.report.builder import (
    GLOBAL_CAVEAT,
    FindingRow,
    FullReport,
    ReportSection,
    SourceListing,
    build_full_report,
)
from huisChecker.report.modules import (
    ReportModuleContract,
    ReportModuleKey,
    ReportModuleRegistry,
    report_module_registry,
)

__all__ = [
    "FindingRow",
    "FullReport",
    "GLOBAL_CAVEAT",
    "ReportModuleContract",
    "ReportModuleKey",
    "ReportModuleRegistry",
    "ReportSection",
    "SourceListing",
    "build_full_report",
    "report_module_registry",
]
