"""CBS PC4/regional statistics adapter.

Live path targets CBS OData StatLine for postcode kerncijfers; when that
call fails or the pc4 is out-of-scope, the adapter falls back to the
cached payload and then to curated CSV. Only scope-relevant pc4s are
ever fetched; broad national downloads are never triggered here.
"""

from __future__ import annotations

import os
from pathlib import Path

from huisChecker.etl.io import read_csv
from huisChecker.remote.cache import cache_get, cache_put
from huisChecker.scope import current_scope

ADAPTER = "cbs"
CBS_DATASET_DEFAULT = "85318NED"  # Kerncijfers wijken en buurten (postcode variant)


def _timeout() -> float:
    try:
        return float(os.getenv("REMOTE_TIMEOUT_SECONDS", "4"))
    except ValueError:
        return 4.0


def fetch_pc4(pc4: str, *, data_root: Path | None = None) -> dict | None:
    """Return `{"population_density": float, "reference_period": str, "source": "..."}` or None.

    Remote HTTP is scope-gated; the curated-subset fallback always runs
    so already-curated out-of-scope rows keep rendering.
    """
    if not pc4:
        return None
    if current_scope().contains_pc4(pc4):
        cached = cache_get(ADAPTER, pc4)
        if cached:
            return cached
        live = _fetch_live(pc4)
        if live:
            cache_put(ADAPTER, pc4, live)
            return live
    return _fallback_curated(pc4, data_root=data_root)


def _fetch_live(pc4: str) -> dict | None:
    base = os.getenv("CBS_BASE_URL", "https://opendata.cbs.nl/ODataApi/odata").rstrip("/")
    dataset = os.getenv("CBS_DATASET", CBS_DATASET_DEFAULT)
    try:
        import httpx  # lazy import keeps import-time cheap for tests
    except Exception:
        return None
    url = f"{base}/{dataset}/TypedDataSet"
    params = {"$filter": f"Postcode eq 'PC{pc4}'", "$top": "1"}
    try:
        with httpx.Client(timeout=_timeout()) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
        rows = (resp.json() or {}).get("value") or []
    except Exception:
        return None
    if not rows:
        return None
    row = rows[0]
    density = row.get("Bevolkingsdichtheid_33") or row.get("population_density")
    try:
        density_f = float(density) if density is not None else None
    except (TypeError, ValueError):
        density_f = None
    if density_f is None:
        return None
    return {
        "postcode4": pc4,
        "population_density": density_f,
        "reference_period": str(row.get("Perioden") or row.get("reference_period") or ""),
        "source": f"CBS StatLine {dataset}",
    }


def _fallback_curated(pc4: str, *, data_root: Path | None = None) -> dict | None:
    root = data_root if data_root is not None else Path(os.getenv("DATA_DIR", "data"))
    overview = root / "curated" / "postcode4_overview.csv"
    if not overview.exists():
        return None
    for row in read_csv(overview):
        if row.get("postcode4") == pc4 and row.get("population_density"):
            return {
                "postcode4": pc4,
                "population_density": float(row["population_density"]),
                "reference_period": "",
                "source": "lokale subset (CBS)",
            }
    return None


__all__ = ["ADAPTER", "fetch_pc4"]
