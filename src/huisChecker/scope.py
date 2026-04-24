"""Current-phase geographic scope for remote adapters and local caching.

The app deliberately narrows to a small test footprint so that remote
calls, on-disk caches, and curated subsets stay small and verifiable.
Defaults cover the MVP test address (Maresingel 29, Leiden 2316HB) and
its containing municipality + province. Envs `HC_SCOPE_PC4`,
`HC_SCOPE_MUNICIPALITIES`, `HC_SCOPE_PROVINCES` accept comma-separated
lists to expand scope without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_PC4 = ("2316",)
DEFAULT_MUNICIPALITIES = ("GM0546",)  # Leiden
DEFAULT_PROVINCES = ("PV28",)  # Zuid-Holland
DEFAULT_MUNICIPALITY_NAMES = ("Leiden",)
DEFAULT_PROVINCE_NAMES = ("Zuid-Holland",)


def _split_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if not raw:
        return default
    return tuple(v.strip() for v in raw.split(",") if v.strip())


@dataclass(frozen=True)
class Scope:
    pc4: tuple[str, ...] = field(default_factory=lambda: DEFAULT_PC4)
    municipalities: tuple[str, ...] = field(default_factory=lambda: DEFAULT_MUNICIPALITIES)
    provinces: tuple[str, ...] = field(default_factory=lambda: DEFAULT_PROVINCES)
    municipality_names: tuple[str, ...] = field(default_factory=lambda: DEFAULT_MUNICIPALITY_NAMES)
    province_names: tuple[str, ...] = field(default_factory=lambda: DEFAULT_PROVINCE_NAMES)

    def contains_pc4(self, pc4: str | None) -> bool:
        return bool(pc4) and pc4 in self.pc4

    def contains_municipality(self, code: str | None) -> bool:
        return bool(code) and code in self.municipalities

    def contains_province(self, code: str | None) -> bool:
        return bool(code) and code in self.provinces

    def covers(self, *, pc4: str | None, municipality: str | None, province: str | None) -> bool:
        """Loose containment: any matching key counts as in-scope."""
        return (
            self.contains_pc4(pc4)
            or self.contains_municipality(municipality)
            or self.contains_province(province)
        )


def current_scope() -> Scope:
    return Scope(
        pc4=_split_env("HC_SCOPE_PC4", DEFAULT_PC4),
        municipalities=_split_env("HC_SCOPE_MUNICIPALITIES", DEFAULT_MUNICIPALITIES),
        provinces=_split_env("HC_SCOPE_PROVINCES", DEFAULT_PROVINCES),
        municipality_names=_split_env("HC_SCOPE_MUNICIPALITY_NAMES", DEFAULT_MUNICIPALITY_NAMES),
        province_names=_split_env("HC_SCOPE_PROVINCE_NAMES", DEFAULT_PROVINCE_NAMES),
    )


__all__ = ["Scope", "current_scope"]
