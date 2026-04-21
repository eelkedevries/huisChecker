from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from huisChecker.contracts import (
    Address,
    AreaMetricSnapshot,
    ComparisonMode,
    GeographyLevel,
    MetricDefinition,
    MetricRegistry,
    canonical_address_id,
    metric_registry,
    postcode4_of,
)


def test_canonical_address_id_normalises_postcode_and_addition() -> None:
    assert canonical_address_id("1011 AB", 12, "a") == "1011AB-12-A"
    assert canonical_address_id("1011ab", 12, None) == "1011AB-12"
    assert postcode4_of("1011 AB") == "1011"


@pytest.mark.parametrize("bad", ["011AB", "1011A", "10111AB", "abcdefg"])
def test_invalid_postcode_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        canonical_address_id(bad, 1, None)


def test_address_validates_identifiers() -> None:
    addr = Address(
        id=canonical_address_id("1011AB", 12, None),
        postcode="1011AB",
        house_number=12,
        street="Damrak",
        city="Amsterdam",
        postcode4="1011",
        municipality_code="GM0363",
        province_code="PV27",
    )
    assert addr.id == "1011AB-12"
    assert addr.postcode4 == "1011"


def test_address_rejects_bad_bag_id() -> None:
    with pytest.raises(ValidationError):
        Address(
            id="1011AB-12",
            postcode="1011AB",
            house_number=12,
            street="Damrak",
            city="Amsterdam",
            postcode4="1011",
            municipality_code="GM0363",
            province_code="PV27",
            bag_object_id="not-a-bag-id",
        )


def test_area_metric_snapshot_requires_period_and_source() -> None:
    snap = AreaMetricSnapshot(
        metric_key="cbs_population_density",
        geography_level=GeographyLevel.POSTCODE4.value,
        geography_code="1011",
        value=Decimal("6421.0"),
        unit="inhabitants/km2",
        reference_period="2024",
        source_dataset_key="cbs_kerncijfers_pc4",
        computed_at=datetime.now(tz=UTC),
    )
    assert snap.value == Decimal("6421.0")


def test_metric_registry_blocks_duplicate_registration() -> None:
    reg = MetricRegistry()
    d = MetricDefinition(
        key="x_test",
        label="x",
        geography_level=GeographyLevel.POSTCODE4,
        source_dataset_key="src",
        unit=None,
        caveat="c",
        preferred_comparison=ComparisonMode.NONE,
    )
    reg.register(d)
    with pytest.raises(ValueError):
        reg.register(d)


def test_seeded_metric_registry_covers_each_source_group() -> None:
    sources = {m.source_dataset_key for m in metric_registry.all()}
    for required in (
        "cbs_kerncijfers_pc4",
        "bag",
        "leefbaarometer",
        "politie_opendata",
        "klimaateffectatlas",
    ):
        assert required in sources


def test_leefbaarometer_uses_source_native_comparison() -> None:
    m = metric_registry.get("leefbaarometer_score")
    assert m.preferred_comparison is ComparisonMode.SOURCE_NATIVE
