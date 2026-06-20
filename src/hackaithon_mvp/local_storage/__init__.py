"""Local storage adapter package for the HackAIthon MVP."""

from .availability_index import build_availability_index, check_storage_readiness_against_requirements
from .parquet_adapter import (
    detect_parquet_capability,
    read_dataset_records,
    read_records,
    validate_market_bar_records,
    write_dataset_records,
    write_records,
)
from .storage_paths import build_partition_path, normalize_dataset_kind

__all__ = [
    "build_availability_index",
    "build_partition_path",
    "check_storage_readiness_against_requirements",
    "detect_parquet_capability",
    "normalize_dataset_kind",
    "read_dataset_records",
    "read_records",
    "validate_market_bar_records",
    "write_dataset_records",
    "write_records",
]
