"""Dependency-safe local parquet-compatible adapter."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.data_contracts import BarRecord

from .storage_paths import build_partition_path


NON_CLAIM_TEXT = "Local storage adapter only; no database, data gateway, live data access, or provider calls."
CLAIM_BOUNDARY = {
    "local_files_only": True,
    "database_created": False,
    "data_gateway_created": False,
    "live_data_enabled": False,
    "provider_calls_enabled": False,
    "training_performed": False,
    "inference_performed": False,
    "benchmark_rerun": False,
}
REQUIRED_MARKET_BAR_FIELDS = ("ticker", "timeframe", "timestamp", "open", "high", "low", "close", "volume")


def _find_parquet_engine() -> str | None:
    for engine in ("pyarrow", "fastparquet"):
        if importlib.util.find_spec(engine) is not None:
            return engine
    return None


def detect_parquet_capability() -> dict:
    pandas_available = importlib.util.find_spec("pandas") is not None
    engine = _find_parquet_engine() if pandas_available else None
    parquet_available = pandas_available and engine is not None
    return {
        "pandas_available": pandas_available,
        "parquet_engine": engine,
        "parquet_engine_available": parquet_available,
        "storage_format": "parquet" if parquet_available else "jsonl_fallback",
        "fallback_format": "jsonl",
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _as_path(path: str) -> Path:
    text = str(path).strip()
    if not text:
        raise ValueError("path must be non-empty")
    return Path(text)


def _fallback_path(path: Path) -> Path:
    if path.suffix.lower() == ".jsonl":
        return path
    return path.with_suffix(".jsonl")


def _validate_records(records: tuple[dict, ...]) -> tuple[dict, ...]:
    if not isinstance(records, tuple):
        raise ValueError("records must be a tuple of dictionaries")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("records must contain dictionaries only")
    return tuple(dict(record) for record in records)


def _json_safe_record(record: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(record, sort_keys=True, default=str))


def _write_jsonl(path: Path, records: tuple[dict, ...]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(_json_safe_record(record), sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> tuple[dict, ...]:
    if not path.exists():
        return ()
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return tuple(rows)


def write_records(path: str, records: tuple[dict, ...]) -> dict:
    """Write records to parquet when possible, otherwise JSONL fallback."""

    requested_path = _as_path(path)
    normalized_records = _validate_records(records)
    capability = detect_parquet_capability()
    requested_path.parent.mkdir(parents=True, exist_ok=True)

    if capability["parquet_engine_available"] and requested_path.suffix.lower() == ".parquet":
        import pandas as pd

        frame = pd.DataFrame([_json_safe_record(record) for record in normalized_records])
        frame.to_parquet(requested_path, engine=capability["parquet_engine"], index=False)
        actual_path = requested_path
        storage_format = "parquet"
    else:
        actual_path = _fallback_path(requested_path)
        actual_path.parent.mkdir(parents=True, exist_ok=True)
        _write_jsonl(actual_path, normalized_records)
        storage_format = "jsonl_fallback"

    return {
        "requested_path": str(requested_path).replace("\\", "/"),
        "actual_path": str(actual_path).replace("\\", "/"),
        "row_count": len(normalized_records),
        "storage_format": storage_format,
        "parquet_engine_available": bool(capability["parquet_engine_available"]),
        "parquet_engine": capability["parquet_engine"],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def read_records(path: str) -> tuple[dict, ...]:
    requested_path = _as_path(path)
    capability = detect_parquet_capability()
    if requested_path.suffix.lower() == ".parquet" and capability["parquet_engine_available"] and requested_path.exists():
        import pandas as pd

        return tuple(pd.read_parquet(requested_path, engine=capability["parquet_engine"]).to_dict(orient="records"))
    fallback = _fallback_path(requested_path)
    return _read_jsonl(fallback if fallback.exists() else requested_path)


def write_dataset_records(
    root: str,
    dataset_kind: str,
    records: tuple[dict, ...],
    *,
    ticker: str | None = None,
    timeframe: str | None = None,
    date: str | None = None,
    run_id: str | None = None,
) -> dict:
    path = build_partition_path(root, dataset_kind, ticker=ticker, timeframe=timeframe, date=date, run_id=run_id)
    if not path.endswith(".parquet"):
        path = f"{path.rstrip('/')}/part.parquet"
    return write_records(path, records)


def read_dataset_records(
    root: str,
    dataset_kind: str,
    *,
    ticker: str | None = None,
    timeframe: str | None = None,
    date: str | None = None,
    run_id: str | None = None,
) -> tuple[dict, ...]:
    path = build_partition_path(root, dataset_kind, ticker=ticker, timeframe=timeframe, date=date, run_id=run_id)
    if not path.endswith(".parquet"):
        path = f"{path.rstrip('/')}/part.parquet"
    return read_records(path)


def validate_market_bar_records(records: tuple[dict, ...]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(records, tuple):
        return {"is_valid": False, "row_count": 0, "errors": ["records must be a tuple"], "warnings": []}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"row {index}: record must be a dictionary")
            continue
        missing = [field for field in REQUIRED_MARKET_BAR_FIELDS if field not in record]
        if missing:
            errors.append(f"row {index}: missing required fields: {missing}")
            continue
        try:
            BarRecord(**{field: record.get(field) for field in (*REQUIRED_MARKET_BAR_FIELDS, "source", "adjusted_close", "metadata") if field in record})
        except ValueError as exc:
            errors.append(f"row {index}: {exc}")
    return {
        "is_valid": not errors,
        "row_count": len(records),
        "errors": errors,
        "warnings": warnings,
    }
