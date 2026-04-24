"""Politie open-data adapter.

Live access to politie.nl open data needs gemeente + wijkcode, not PC4,
so fetching is anchored on the scoped municipality. The adapter returns
per-PC4 incident rates where available and caches the most recent
scope slice. Out-of-scope pc4 → None; live failure → cache → curated.
"""

from __future__ import annotations

import os
from pathlib import Path

from huisChecker.etl.io import read_csv
from huisChecker.remote.cache import cache_get, cache_put
from huisChecker.scope import current_scope

ADAPTER = "politie"


def _timeout() -> float:
    try:
        return float(os.getenv("REMOTE_TIMEOUT_SECONDS", "4"))
    except ValueError:
        return 4.0


def fetch_pc4(
    pc4: str,
    *,
    municipality_code: str | None = None,
    data_root: Path | None = None,
) -> dict | None:
    if not pc4:
        return None
    scope = current_scope()
    in_scope = scope.contains_pc4(pc4) or scope.contains_municipality(municipality_code)
    if in_scope:
        cached = cache_get(ADAPTER, pc4)
        if cached:
            return cached
        live = _fetch_live(pc4, municipality_code)
        if live:
            cache_put(ADAPTER, pc4, live)
            return live
    return _fallback_curated(pc4, data_root=data_root)


def _fetch_live(pc4: str, municipality_code: str | None) -> dict | None:
    base = os.getenv("POLITIE_BASE_URL", "").rstrip("/")
    if not base:
        return None
    try:
        import httpx
    except Exception:
        return None
    params = {"postcode4": pc4}
    if municipality_code:
        params["gemeente"] = municipality_code
    try:
        with httpx.Client(timeout=_timeout()) as client:
            resp = client.get(f"{base}/incidents", params=params)
            resp.raise_for_status()
        data = resp.json() or {}
    except Exception:
        return None
    total = data.get("total_incidents")
    rate = data.get("incidents_per_1000")
    try:
        rate_f = float(rate) if rate is not None else None
    except (TypeError, ValueError):
        rate_f = None
    if rate_f is None:
        return None
    return {
        "postcode4": pc4,
        "total_incidents": total,
        "incidents_per_1000": rate_f,
        "reference_period": str(data.get("reference_period") or ""),
        "source": "politie open data",
    }


def _fallback_curated(pc4: str, *, data_root: Path | None = None) -> dict | None:
    root = data_root if data_root is not None else Path(os.getenv("DATA_DIR", "data"))
    path = root / "curated" / "politie_pc4_incidents.csv"
    if not path.exists():
        return None
    for row in read_csv(path):
        if row.get("postcode4") == pc4 and row.get("incidents_per_1000"):
            return {
                "postcode4": pc4,
                "total_incidents": row.get("total_incidents"),
                "incidents_per_1000": float(row["incidents_per_1000"]),
                "reference_period": row.get("reference_period", ""),
                "source": "lokale subset (politie)",
            }
    return None


__all__ = ["ADAPTER", "fetch_pc4"]
