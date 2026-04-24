"""Tiny on-disk cache for remote adapter payloads.

Files live at `<DATA_DIR>/cache/<adapter>/<key>.json`. Reads and writes
are best-effort: a corrupt or unreadable file returns None rather than
raising, so the preview/report always have a graceful path back to the
minimal local subset.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _data_root() -> Path:
    return Path(os.getenv("DATA_DIR", "data"))


def cache_root() -> Path:
    return _data_root() / "cache"


def _file(adapter: str, key: str) -> Path:
    safe = "".join(ch for ch in key if ch.isalnum() or ch in ("-", "_"))
    return cache_root() / adapter / f"{safe or 'default'}.json"


def cache_get(adapter: str, key: str) -> Any | None:
    path = _file(adapter, key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def cache_put(adapter: str, key: str, payload: Any) -> Path | None:
    path = _file(adapter, key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        return None
    return path


__all__ = ["cache_get", "cache_put", "cache_root"]
