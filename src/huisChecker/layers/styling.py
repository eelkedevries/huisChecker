"""Resolve display properties (color, band label) for a layer feature.

Kept free of rendering concerns so both server-side geojson enrichment
and tests can call the same pure functions.
"""

from __future__ import annotations

from typing import Any

from huisChecker.layers.definitions import LayerDefinition, LegendStop, LegendType


def resolve_stop(layer: LayerDefinition, properties: dict[str, Any]) -> LegendStop | None:
    legend = layer.legend
    if legend is None:
        return None

    prop_key = layer.resolved_feature_property
    if prop_key is None:
        return None

    raw = properties.get(prop_key)
    if raw is None:
        return None

    if legend.type == LegendType.CATEGORICAL:
        return _match_categorical(legend.stops, raw)
    if legend.type in (LegendType.QUANTILE, LegendType.CONTINUOUS):
        value = _coerce_float(raw)
        if value is None:
            return None
        return _match_binned(legend.stops, value, legend.min, legend.max)
    return None


def feature_color(layer: LayerDefinition, properties: dict[str, Any]) -> str | None:
    stop = resolve_stop(layer, properties)
    return stop.color if stop is not None else None


def feature_label(layer: LayerDefinition, properties: dict[str, Any]) -> str | None:
    stop = resolve_stop(layer, properties)
    return stop.label if stop is not None else None


def _match_categorical(stops: tuple[LegendStop, ...], raw: Any) -> LegendStop | None:
    for stop in stops:
        if stop.value is None:
            continue
        if str(stop.value) == str(raw):
            return stop
    return None


def _match_binned(
    stops: tuple[LegendStop, ...],
    value: float,
    legend_min: float | None,
    legend_max: float | None,
) -> LegendStop | None:
    # Equal-width bins across [min, max]. If min/max not provided, fall back
    # to the explicit stop values when present, otherwise the first stop.
    if legend_min is None or legend_max is None or legend_max <= legend_min:
        for stop in stops:
            if stop.value is not None and _coerce_float(stop.value) == value:
                return stop
        return stops[0] if stops else None

    if value <= legend_min:
        return stops[0]
    if value >= legend_max:
        return stops[-1]

    span = legend_max - legend_min
    bin_count = len(stops)
    idx = int((value - legend_min) / span * bin_count)
    idx = max(0, min(bin_count - 1, idx))
    return stops[idx]


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["feature_color", "feature_label", "resolve_stop"]
