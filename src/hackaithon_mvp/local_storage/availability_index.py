"""Availability summaries over local storage records."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


NON_CLAIM_TEXT = "Local availability summary only; no data gateway, live data access, or provider calls."
CLAIM_BOUNDARY = {
    "local_records_only": True,
    "database_created": False,
    "data_gateway_created": False,
    "live_data_enabled": False,
    "provider_calls_enabled": False,
    "training_performed": False,
    "inference_performed": False,
    "benchmark_rerun": False,
}
MISSING_SAMPLE_LIMIT = 10


def _record_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return dict(value) if isinstance(value, dict) else {}


def _requirement_dict(value: Any) -> dict[str, Any]:
    return _record_dict(value)


def build_availability_index(records: tuple[dict, ...]) -> dict:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for record_value in records:
        record = _record_dict(record_value)
        if not {"ticker", "timeframe", "timestamp"}.issubset(record):
            continue
        ticker = str(record["ticker"]).strip().upper()
        if not ticker:
            continue
        timeframe = normalize_timeframe(str(record["timeframe"]))
        timestamp = str(record["timestamp"]).strip()
        key = (ticker, timeframe)
        group = groups.setdefault(
            key,
            {
                "ticker": ticker,
                "timeframe": timeframe,
                "bar_count": 0,
                "min_timestamp": timestamp,
                "max_timestamp": timestamp,
            },
        )
        group["bar_count"] += 1
        group["min_timestamp"] = min(group["min_timestamp"], timestamp)
        group["max_timestamp"] = max(group["max_timestamp"], timestamp)

    ordered_groups = [
        groups[key]
        for key in sorted(groups)
    ]
    return {
        "groups": ordered_groups,
        "group_count": len(ordered_groups),
        "total_records": len(records),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _available_map(index: dict) -> dict[tuple[str, str], int]:
    mapping: dict[tuple[str, str], int] = {}
    for group in index.get("groups", []) or []:
        if not isinstance(group, dict):
            continue
        ticker = str(group.get("ticker", "")).strip().upper()
        timeframe = normalize_timeframe(str(group.get("timeframe", "")))
        mapping[(ticker, timeframe)] = int(group.get("bar_count", 0))
    return mapping


def _required_bars(requirement: dict[str, Any]) -> int:
    for field in ("required_bars", "lookback_bars", "cases_required"):
        if field in requirement and requirement[field] is not None:
            return int(requirement[field])
    return 1


def check_storage_readiness_against_requirements(
    availability_index: dict,
    requirements: tuple[dict, ...],
) -> dict:
    availability = _available_map(availability_index)
    ready_count = 0
    missing_sample: list[dict[str, Any]] = []
    for requirement_value in requirements:
        requirement = _requirement_dict(requirement_value)
        ticker = str(requirement.get("ticker", "")).strip().upper()
        timeframe_value = requirement.get("canonical_timeframe", requirement.get("timeframe"))
        timeframe = normalize_timeframe(str(timeframe_value))
        required = _required_bars(requirement)
        available = availability.get((ticker, timeframe), 0)
        if available >= required:
            ready_count += 1
        elif len(missing_sample) < MISSING_SAMPLE_LIMIT:
            missing_sample.append(
                {
                    "ticker": ticker,
                    "timeframe": timeframe,
                    "required_bars": required,
                    "available_bars": available,
                    "shortfall_bars": max(0, required - available),
                }
            )

    requirements_count = len(requirements)
    missing_count = requirements_count - ready_count
    coverage_ratio = round(ready_count / requirements_count, 6) if requirements_count else 0.0
    return {
        "requirements_count": requirements_count,
        "ready_count": ready_count,
        "missing_count": missing_count,
        "coverage_ratio": coverage_ratio,
        "missing_sample": missing_sample,
        "non_claim": NON_CLAIM_TEXT,
    }
