"""Leefbaarometer ETL: source-native scores per postcode4.

Produces:
  - data/curated/leefbaarometer_pc4.csv
  - data/curated/layers/leefbaarometer_pc4.geojson  (band-coloured stub)

When the fixture carries dimension scores (the five official Leefbaarometer
3.0 dimensions) they are passed through unchanged as extra CSV columns and
geojson feature properties. No synthetic aggregation is produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from huisChecker.contracts import AreaMetricSnapshot, GeographyLevel
from huisChecker.etl.base import ETLJob, ETLResult, SourceMode
from huisChecker.etl.geometry_stubs import available_pc4s, pc4_feature
from huisChecker.etl.io import read_json, write_csv, write_json
from huisChecker.etl.manifest import SourceManifest, now_iso, write_manifest

# Official Leefbaarometer 3.0 dimensions. Order matters for display.
DIMENSION_KEYS: tuple[str, ...] = (
    "woningvoorraad",
    "fysieke_omgeving",
    "voorzieningen",
    "sociale_samenhang",
    "overlast_en_onveiligheid",
)


@dataclass(frozen=True)
class _LbNormalised:
    reference_period: str
    metrics: tuple[AreaMetricSnapshot, ...]
    bands: tuple[tuple[str, str], ...]  # (postcode4, band)
    dimensions: dict[str, dict[str, Decimal]]  # pc4 -> {dim_key: value}


class LeefbaarometerJob(ETLJob):
    source_key = "leefbaarometer"
    label = "Leefbaarometer 3.0"
    caveat = "Samengestelde score gepubliceerd door Leefbaarometer; getoond zoals gepubliceerd."

    def extract(self) -> dict[str, Any]:
        if self.ctx.mode is SourceMode.FIXTURE:
            return read_json(self.ctx.fixtures_root / "leefbaarometer.json")
        raise NotImplementedError("Leefbaarometer live extraction not implemented in MVP.")

    def normalise(self, raw: dict[str, Any]) -> _LbNormalised:
        period = raw["reference_period"]
        now = datetime.now(tz=UTC)
        metrics = tuple(
            AreaMetricSnapshot(
                metric_key="leefbaarometer_score",
                geography_level=GeographyLevel.POSTCODE4.value,
                geography_code=row["postcode4"],
                value=Decimal(str(row["score"])),
                unit=None,
                reference_period=period,
                source_dataset_key=self.source_key,
                computed_at=now,
            )
            for row in raw["pc4_scores"]
        )
        bands = tuple((row["postcode4"], row["band"]) for row in raw["pc4_scores"])
        dimensions: dict[str, dict[str, Decimal]] = {}
        for row in raw["pc4_scores"]:
            dims = row.get("dimensions") or {}
            if not dims:
                continue
            dimensions[row["postcode4"]] = {
                k: Decimal(str(dims[k])) for k in DIMENSION_KEYS if k in dims
            }
        return _LbNormalised(
            reference_period=period, metrics=metrics, bands=bands, dimensions=dimensions
        )

    def load(self, n: _LbNormalised) -> ETLResult:
        curated = self.ctx.curated_root
        outputs: list = []
        csv_columns = (
            "postcode4",
            "score",
            "band",
            "reference_period",
            "source_dataset_key",
            *DIMENSION_KEYS,
        )
        outputs.append(
            write_csv(
                curated / "leefbaarometer_pc4.csv",
                [
                    _csv_row(m, n)
                    for m in n.metrics
                ],
                columns=csv_columns,
            )
        )
        score_by_pc4 = {m.geography_code: m.value for m in n.metrics}
        band_by_pc4 = dict(n.bands)
        # Emit one feature per PC4 in the authoritative boundary table.
        # PC4s without a Leefbaarometer score render as no-data cells,
        # so the overlay stays a complete choropleth rather than a set
        # of island polygons.
        rendered_pc4s = sorted(set(available_pc4s()) | set(band_by_pc4))
        layer = {
            "type": "FeatureCollection",
            "reference_period": n.reference_period,
            "features": [
                pc4_feature(
                    pc4,
                    _feature_properties(
                        pc4,
                        band_by_pc4.get(pc4),
                        score_by_pc4,
                        n.dimensions,
                        n.reference_period,
                    ),
                )
                for pc4 in rendered_pc4s
            ],
        }
        outputs.append(write_json(curated / "layers" / "leefbaarometer_pc4.geojson", layer))
        write_manifest(
            self.ctx.manifests_root,
            SourceManifest(
                source_key=self.source_key,
                label=self.label,
                provider="Ministerie van BZK",
                mode=self.ctx.mode.value,
                reference_period=n.reference_period,
                retrieved_at=now_iso(),
                rows_ingested=len(n.metrics),
                outputs=tuple(str(p.relative_to(self.ctx.data_root)) for p in outputs),
                caveats=(self.caveat,),
                licence="CC-BY",
            ),
        )
        return ETLResult(
            source_key=self.source_key,
            rows_ingested=len(n.metrics),
            outputs=tuple(outputs),
            caveats=(self.caveat,),
            reference_period=n.reference_period,
        )


def _csv_row(m: AreaMetricSnapshot, n: _LbNormalised) -> dict[str, Any]:
    row: dict[str, Any] = {
        "postcode4": m.geography_code,
        "score": m.value,
        "band": dict(n.bands).get(m.geography_code, ""),
        "reference_period": m.reference_period,
        "source_dataset_key": m.source_dataset_key,
    }
    dims = n.dimensions.get(m.geography_code, {})
    for key in DIMENSION_KEYS:
        row[key] = dims.get(key, "")
    return row


def _feature_properties(
    pc4: str,
    band: str | None,
    score_by_pc4: dict[str, Decimal],
    dimensions: dict[str, dict[str, Decimal]],
    reference_period: str,
) -> dict[str, Any]:
    props: dict[str, Any] = {
        "postcode4": pc4,
        "reference_period": reference_period,
    }
    if band:
        props["band"] = band
    else:
        # PC4 has an authoritative polygon but no Leefbaarometer score.
        # Mark it so the map renders a no-data cell instead of omitting
        # the area entirely.
        props["no_data"] = True
    if pc4 in score_by_pc4:
        props["leefbaarometer_score"] = float(score_by_pc4[pc4])
    dims = dimensions.get(pc4, {})
    for key in DIMENSION_KEYS:
        if key in dims:
            props[f"dim_{key}"] = float(dims[key])
    return props


__all__ = ["DIMENSION_KEYS", "LeefbaarometerJob"]
