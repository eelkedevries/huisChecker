"""BAG / PDOK address and building ETL.

Produces:
  - data/curated/addresses.csv        (address lookup table)
  - data/curated/bag_objects.csv      (building facts)
  - data/curated/layers/bag_footprints.geojson  (stub reference layer)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from huisChecker.contracts import Address, BagObject, canonical_address_id
from huisChecker.etl.base import ETLJob, ETLResult, SourceMode
from huisChecker.etl.io import read_json, write_csv, write_json
from huisChecker.etl.manifest import SourceManifest, now_iso, write_manifest


@dataclass(frozen=True)
class _BagNormalised:
    reference_period: str
    addresses: tuple[Address, ...]
    bag_objects: tuple[BagObject, ...]


class BagJob(ETLJob):
    source_key = "bag"
    label = "BAG / PDOK address and building registry"
    caveat = "BAG-data betreft geregistreerde feiten; de werkelijke situatie kan afwijken."

    def extract(self) -> dict[str, Any]:
        if self.ctx.mode is SourceMode.FIXTURE:
            return read_json(self.ctx.fixtures_root / "bag.json")
        raise NotImplementedError(
            "BAG live extraction is not implemented in the MVP. "
            "Run with mode=fixture until PDOK snapshot ingestion is wired up."
        )

    def normalise(self, raw: dict[str, Any]) -> _BagNormalised:
        period = raw["reference_period"]
        addresses = tuple(
            Address(
                id=canonical_address_id(
                    row["postcode"], row["house_number"], row.get("house_number_addition")
                ),
                postcode=row["postcode"],
                house_number=row["house_number"],
                house_number_addition=row.get("house_number_addition"),
                street=row["street"],
                city=row["city"],
                nummeraanduiding_id=row.get("nummeraanduiding_id"),
                bag_object_id=row.get("bag_object_id"),
                postcode4=row["postcode4"],
                municipality_code=row["municipality_code"],
                province_code=row["province_code"],
            )
            for row in raw["addresses"]
        )
        bag_objects = tuple(
            BagObject(
                id=row["id"],
                construction_year=row.get("construction_year"),
                use_purpose=tuple(row.get("use_purpose", ())),
                surface_area_m2=row.get("surface_area_m2"),
                latitude=row.get("latitude"),
                longitude=row.get("longitude"),
            )
            for row in raw["bag_objects"]
        )
        return _BagNormalised(
            reference_period=period, addresses=addresses, bag_objects=bag_objects
        )

    def load(self, n: _BagNormalised) -> ETLResult:
        curated = self.ctx.curated_root
        outputs: list = []
        outputs.append(
            write_csv(
                curated / "addresses.csv",
                [
                    {
                        "id": a.id,
                        "postcode": a.postcode,
                        "house_number": a.house_number,
                        "house_number_addition": a.house_number_addition,
                        "street": a.street,
                        "city": a.city,
                        "nummeraanduiding_id": a.nummeraanduiding_id,
                        "bag_object_id": a.bag_object_id,
                        "postcode4": a.postcode4,
                        "municipality_code": a.municipality_code,
                        "province_code": a.province_code,
                    }
                    for a in n.addresses
                ],
                columns=(
                    "id",
                    "postcode",
                    "house_number",
                    "house_number_addition",
                    "street",
                    "city",
                    "nummeraanduiding_id",
                    "bag_object_id",
                    "postcode4",
                    "municipality_code",
                    "province_code",
                ),
            )
        )
        outputs.append(
            write_csv(
                curated / "bag_objects.csv",
                [
                    {
                        "id": b.id,
                        "construction_year": b.construction_year,
                        "use_purpose": ";".join(b.use_purpose),
                        "surface_area_m2": b.surface_area_m2,
                        "latitude": b.latitude,
                        "longitude": b.longitude,
                    }
                    for b in n.bag_objects
                ],
                columns=(
                    "id",
                    "construction_year",
                    "use_purpose",
                    "surface_area_m2",
                    "latitude",
                    "longitude",
                ),
            )
        )
        footprints = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"bag_object_id": b.id},
                    "geometry": {"type": "Point", "coordinates": [b.longitude, b.latitude]},
                }
                for b in n.bag_objects
                if b.latitude is not None and b.longitude is not None
            ],
        }
        outputs.append(write_json(curated / "layers" / "bag_footprints.geojson", footprints))
        rows = len(n.addresses) + len(n.bag_objects)
        write_manifest(
            self.ctx.manifests_root,
            SourceManifest(
                source_key=self.source_key,
                label=self.label,
                provider="Kadaster / PDOK",
                mode=self.ctx.mode.value,
                reference_period=n.reference_period,
                retrieved_at=now_iso(),
                rows_ingested=rows,
                outputs=tuple(str(p.relative_to(self.ctx.data_root)) for p in outputs),
                caveats=(self.caveat,),
                licence="CC0",
                notes="MVP uses a fixture snapshot; footprints layer is a point stub.",
            ),
        )
        return ETLResult(
            source_key=self.source_key,
            rows_ingested=rows,
            outputs=tuple(outputs),
            caveats=(self.caveat,),
            reference_period=n.reference_period,
        )


__all__ = ["BagJob"]
