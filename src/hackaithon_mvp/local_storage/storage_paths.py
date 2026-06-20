"""Stable local dataset path planning for small MVP storage artifacts."""

from __future__ import annotations

import re

from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


SUPPORTED_DATASET_KINDS = frozenset(
    {
        "market_bars",
        "forecast_outputs",
        "actual_outcomes",
        "evaluation_metrics",
        "evidence_packets",
        "diagnostic_reports",
        "dag_runs",
    }
)
BARS_AND_OUTCOMES = frozenset({"market_bars", "actual_outcomes"})
RUN_SCOPED_DATASETS = frozenset(
    {"forecast_outputs", "evaluation_metrics", "evidence_packets", "diagnostic_reports", "dag_runs"}
)
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.=-]+$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean_root(root: str) -> str:
    text = str(root).strip().replace("\\", "/").rstrip("/")
    if not text:
        raise ValueError("root must be non-empty")
    parts = [part for part in text.split("/") if part]
    if any(part == ".." for part in parts):
        raise ValueError("root contains unsupported path characters")
    return text


def _safe_segment(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    if "/" in text or "\\" in text or ".." in text or not _SAFE_SEGMENT.fullmatch(text):
        raise ValueError(f"{field_name} contains unsupported path characters")
    return text


def _normalize_ticker(value: str) -> str:
    return _safe_segment(value, "ticker").upper()


def _normalize_date(value: str) -> str:
    date = _safe_segment(value, "date")
    if not _DATE_PATTERN.fullmatch(date):
        raise ValueError("date must use YYYY-MM-DD format")
    return date


def normalize_dataset_kind(kind: str) -> str:
    normalized = _safe_segment(str(kind).strip().lower(), "dataset_kind")
    if normalized not in SUPPORTED_DATASET_KINDS:
        raise ValueError(f"unsupported dataset_kind: {kind!r}")
    return normalized


def build_partition_path(
    root: str,
    dataset_kind: str,
    ticker: str | None = None,
    timeframe: str | None = None,
    date: str | None = None,
    run_id: str | None = None,
) -> str:
    """Build a stable partition path with forward slashes."""

    clean_root = _clean_root(root)
    kind = normalize_dataset_kind(dataset_kind)
    parts = [clean_root, kind]

    if kind in BARS_AND_OUTCOMES:
        if ticker is not None:
            parts.append(f"ticker={_normalize_ticker(ticker)}")
        if timeframe is not None:
            parts.append(f"timeframe={normalize_timeframe(str(timeframe))}")
        if date is not None:
            parts.append(f"date={_normalize_date(date)}")
        if all(value is not None for value in (ticker, timeframe, date)):
            parts.append("part.parquet")
        return "/".join(parts)

    if run_id is not None:
        parts.append(f"run_id={_safe_segment(run_id, 'run_id')}")
        parts.append("part.parquet")
    return "/".join(parts)
