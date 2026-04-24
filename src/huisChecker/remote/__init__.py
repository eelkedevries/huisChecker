"""Remote-first source adapters.

Each adapter exposes `fetch_pc4(pc4)` (and `fetch_address(resolved)` where
relevant), returning a plain dict of enrichment fields or None on miss.
Adapters:
  - try live HTTP for in-scope keys (short timeout, any exception -> None)
  - persist successful payloads under `data/cache/<adapter>/<pc4>.json`
  - fall back to the minimal local subset (curated CSV) if both miss

Adapters are intentionally narrow: they return the exact fields the
preview/report need, not bulk dumps. Scope gating lives in
`huisChecker.scope.current_scope()`; out-of-scope keys short-circuit
before any network call.
"""

from huisChecker.remote.cache import cache_get, cache_put, cache_root

__all__ = ["cache_get", "cache_put", "cache_root"]
