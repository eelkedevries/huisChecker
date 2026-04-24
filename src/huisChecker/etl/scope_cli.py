"""Scope-limited cache and subset tooling.

`python -m huisChecker.etl.scope_cli <cmd>`
  refresh   prime the remote-adapter cache for every in-scope pc4
  validate  verify the curated subset and cache cover the scope
  smoke     refresh + validate, suitable for CI smoke runs

Deliberately narrow: only touches the pc4s / municipalities / provinces
from `huisChecker.scope.current_scope()`. Broad national downloads are
never triggered here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from huisChecker.etl.io import read_csv
from huisChecker.remote import bag as bag_adapter
from huisChecker.remote import cbs as cbs_adapter
from huisChecker.remote import klimaat as klimaat_adapter
from huisChecker.remote import leefbaarometer as lb_adapter
from huisChecker.remote import politie as politie_adapter
from huisChecker.scope import current_scope


def _data_root() -> Path:
    import os

    return Path(os.getenv("DATA_DIR", "data"))


def refresh() -> int:
    scope = current_scope()
    root = _data_root()
    hits = 0
    for pc4 in scope.pc4:
        for name, fn in (
            ("cbs", lambda p=pc4: cbs_adapter.fetch_pc4(p, data_root=root)),
            ("leefbaarometer", lambda p=pc4: lb_adapter.fetch_pc4(p, data_root=root)),
            ("politie", lambda p=pc4: politie_adapter.fetch_pc4(p, data_root=root)),
            ("klimaat", lambda p=pc4: klimaat_adapter.fetch_pc4(p, data_root=root)),
        ):
            payload = fn()
            marker = "ok" if payload else "miss"
            print(f"[{marker:>4}] {name:<16} pc4={pc4}")
            if payload:
                hits += 1
    # Prime BAG cache for every curated address inside the scope pc4 set.
    addresses = _load_addresses(root)
    for addr in addresses:
        if addr.get("postcode4") not in scope.pc4:
            continue
        payload = bag_adapter.fetch_object(addr.get("bag_object_id", ""), data_root=root)
        marker = "ok" if payload else "miss"
        print(f"[{marker:>4}] bag              id={addr.get('bag_object_id')}")
        if payload:
            hits += 1
    print(f"refresh: {hits} payload(s) cached")
    return 0


def validate() -> int:
    scope = current_scope()
    root = _data_root()
    errors = 0
    for pc4 in scope.pc4:
        for name, fn in (
            ("cbs", lambda p=pc4: cbs_adapter.fetch_pc4(p, data_root=root)),
            ("leefbaarometer", lambda p=pc4: lb_adapter.fetch_pc4(p, data_root=root)),
            ("politie", lambda p=pc4: politie_adapter.fetch_pc4(p, data_root=root)),
            ("klimaat", lambda p=pc4: klimaat_adapter.fetch_pc4(p, data_root=root)),
        ):
            if fn() is None:
                print(f"[  FAIL] {name} missing for pc4 {pc4}")
                errors += 1
            else:
                print(f"[    ok] {name} pc4={pc4}")
    if errors:
        print(f"validate: {errors} gap(s)")
        return 1
    print("validate: ok")
    return 0


def smoke() -> int:
    refresh_rc = refresh()
    if refresh_rc != 0:
        return refresh_rc
    return validate()


def _load_addresses(root: Path) -> list[dict]:
    path = root / "curated" / "addresses.csv"
    if not path.exists():
        return []
    return read_csv(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="huisChecker-scope")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh")
    sub.add_parser("validate")
    sub.add_parser("smoke")
    args = parser.parse_args(argv)
    if args.cmd == "refresh":
        return refresh()
    if args.cmd == "validate":
        return validate()
    if args.cmd == "smoke":
        return smoke()
    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
