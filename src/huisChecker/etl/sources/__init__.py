"""Per-source ETL jobs for the five MVP source groups."""

from huisChecker.etl.sources.bag import BagJob
from huisChecker.etl.sources.cbs import CbsJob
from huisChecker.etl.sources.klimaat import KlimaatJob
from huisChecker.etl.sources.leefbaarometer import LeefbaarometerJob
from huisChecker.etl.sources.politie import PolitieJob
from huisChecker.etl.sources.registry import CORE_SOURCES, source_registry

__all__ = [
    "BagJob",
    "CORE_SOURCES",
    "CbsJob",
    "KlimaatJob",
    "LeefbaarometerJob",
    "PolitieJob",
    "source_registry",
]
