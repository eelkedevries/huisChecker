"""Runtime configuration helpers.

Small, dependency-free accessors for environment-backed feature flags so
routes, templates, and helpers all see the same value.
"""

from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUTHY


def app_env() -> str:
    return os.getenv("APP_ENV", "development").strip().lower() or "development"


def is_development() -> bool:
    return app_env() == "development"


def report_free_access_enabled() -> bool:
    """Return True when full reports should be accessible without checkout.

    Intended for local/dev testing. Requires `REPORT_FREE_ACCESS=1` AND a
    non-production `APP_ENV`; production never flips to free via env alone.
    """
    if not _truthy(os.getenv("REPORT_FREE_ACCESS", "1" if is_development() else "0")):
        return False
    return is_development()


__all__ = [
    "app_env",
    "is_development",
    "report_free_access_enabled",
]
