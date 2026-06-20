"""Storage design decision contract for future local market bar data."""

from __future__ import annotations

import argparse
import json
import re

from src.hackaithon_mvp.hybrid_storage_architecture import (
    HYBRID_ARCHITECTURE_NAME,
    RECOMMENDED_CURRENT,
    RECOMMENDED_TARGET,
)
from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


STORAGE_BACKEND_DECISION = "local_parquet_dataset_with_duckdb_compatible_query_adapter"
CANONICAL_DATA_FORMAT = "parquet"
PLANNED_QUERY_ADAPTER = "duckdb_compatible"
PARTITION_COLUMNS = ("ticker", "timeframe", "date")
REQUIRED_BAR_COLUMNS = ("ticker", "timeframe", "timestamp", "open", "high", "low", "close", "volume")
OPTIONAL_BAR_COLUMNS = ("adjusted_close", "source", "metadata")
NON_CLAIM_TEXT = "Storage design contract only; no server database, data gateway, or live data access is created."
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _safe_segment(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    if "/" in text or "\\" in text or ".." in text or not _SAFE_SEGMENT.fullmatch(text):
        raise ValueError(f"{field_name} contains unsupported path characters")
    return text


def _normalize_ticker(value: str) -> str:
    return _safe_segment(value, "ticker").upper()


def _validate_date(value: str) -> str:
    date = _safe_segment(value, "date")
    if not _DATE_PATTERN.fullmatch(date):
        raise ValueError("date must use YYYY-MM-DD format")
    return date


def get_storage_design() -> dict:
    return {
        "decision": STORAGE_BACKEND_DECISION,
        "recommended_current": RECOMMENDED_CURRENT,
        "recommended_target": RECOMMENDED_TARGET,
        "hybrid_architecture_enabled": True,
        "hybrid_architecture_module": "src.hackaithon_mvp.hybrid_storage_architecture",
        "storage_target_architecture": HYBRID_ARCHITECTURE_NAME,
        "local_storage_adapter_implemented": True,
        "canonical_data_format": CANONICAL_DATA_FORMAT,
        "planned_query_adapter": PLANNED_QUERY_ADAPTER,
        "partition_columns": list(PARTITION_COLUMNS),
        "required_bar_columns": list(REQUIRED_BAR_COLUMNS),
        "optional_bar_columns": list(OPTIONAL_BAR_COLUMNS),
        "database_created": False,
        "server_database_created": False,
        "data_gateway_created": False,
        "live_data_enabled": False,
        "provider_calls_enabled": False,
        "non_claim": NON_CLAIM_TEXT,
    }


def build_partition_path(root: str, ticker: str, timeframe: str, date: str) -> str:
    clean_root = str(root).strip().replace("\\", "/").rstrip("/")
    if not clean_root:
        raise ValueError("root must be non-empty")
    if ".." in clean_root:
        raise ValueError("root contains unsupported path characters")
    normalized_ticker = _normalize_ticker(ticker)
    canonical_timeframe = normalize_timeframe(timeframe)
    clean_date = _validate_date(date)
    return (
        f"{clean_root}/ticker={normalized_ticker}/timeframe={canonical_timeframe}/"
        f"date={clean_date}/bars.parquet"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Show the HackAIthon MVP storage design contract.")


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    parser.parse_args(argv)
    print(json.dumps(get_storage_design(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
