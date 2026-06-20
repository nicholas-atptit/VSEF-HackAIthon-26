"""Performance attribution for local forecast-actual diagnostic rows."""

from __future__ import annotations

from collections import Counter
from typing import Any

from src.hackaithon_mvp.forecast_actual_evaluation import (
    CLAIM_BOUNDARY as FORECAST_ACTUAL_CLAIM_BOUNDARY,
    DIRECTIONAL_DIAGNOSTICS,
    validate_forecast_actual_row,
)


MIN_DIRECTIONAL_ELIGIBLE_BALANCED_ACCURACY = 0.525
STRONG_BALANCED_ACCURACY = 0.55
WEAK_BALANCED_ACCURACY = 0.50
NON_CLAIM_TEXT = "Diagnostic research output only; local realized rows are required for accuracy."
CLAIM_BOUNDARY = {
    "baseline_ml_only": True,
    "diagnostic_research_only": True,
    "actual_data_required": True,
    "no_live_data": True,
    "no_provider_api_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "no_action_output": True,
}


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _is_correct(row: dict[str, Any]) -> bool | None:
    diagnostic = row["forecast_diagnostic"]
    actual = row["actual_direction_label"]
    if diagnostic == "positive_bias":
        return actual == "positive"
    if diagnostic == "negative_bias":
        return actual == "negative"
    return None


def _group_key(row: dict[str, Any], group_fields: tuple[str, ...]) -> dict[str, str]:
    key: dict[str, str] = {}
    for field in group_fields:
        value = row.get(field)
        key[field] = "unspecified" if value in (None, "") else str(value)
    return key


def _group_key_id(group_key: dict[str, str], group_fields: tuple[str, ...]) -> str:
    return "|".join(f"{field}={group_key[field]}" for field in group_fields)


def _directional_group_metrics(
    rows: tuple[dict[str, Any], ...],
    group_key: dict[str, str],
    group_fields: tuple[str, ...],
    min_sample_count: int,
) -> dict[str, Any]:
    directional_rows = tuple(row for row in rows if row["forecast_diagnostic"] in DIRECTIONAL_DIAGNOSTICS)
    sample_count = len(directional_rows)
    correct_count = len([row for row in directional_rows if _is_correct(row) is True])
    incorrect_count = len([row for row in directional_rows if _is_correct(row) is False])
    positive_predictions = tuple(row for row in directional_rows if row["forecast_diagnostic"] == "positive_bias")
    negative_predictions = tuple(row for row in directional_rows if row["forecast_diagnostic"] == "negative_bias")
    actual_positive = tuple(row for row in directional_rows if row["actual_direction_label"] == "positive")
    actual_negative = tuple(row for row in directional_rows if row["actual_direction_label"] == "negative")
    positive_correct = tuple(row for row in positive_predictions if row["actual_direction_label"] == "positive")
    negative_correct = tuple(row for row in negative_predictions if row["actual_direction_label"] == "negative")
    positive_recall = _ratio(
        len([row for row in actual_positive if row["forecast_diagnostic"] == "positive_bias"]),
        len(actual_positive),
    )
    negative_recall = _ratio(
        len([row for row in actual_negative if row["forecast_diagnostic"] == "negative_bias"]),
        len(actual_negative),
    )
    if positive_recall is None or negative_recall is None:
        balanced_accuracy = None
    else:
        balanced_accuracy = round((positive_recall + negative_recall) / 2, 6)

    sample_sufficient = sample_count >= min_sample_count
    directionally_eligible = (
        sample_sufficient
        and balanced_accuracy is not None
        and balanced_accuracy >= MIN_DIRECTIONAL_ELIGIBLE_BALANCED_ACCURACY
    )
    return {
        "group_key": dict(group_key),
        "group_key_id": _group_key_id(group_key, group_fields),
        "sample_count": sample_count,
        "rows_total": len(rows),
        "correct_directional_rows": correct_count,
        "incorrect_directional_rows": incorrect_count,
        "directional_accuracy": _ratio(correct_count, sample_count),
        "balanced_directional_accuracy": balanced_accuracy,
        "coverage_ratio": _ratio(sample_count, len(rows)),
        "positive_precision": _ratio(len(positive_correct), len(positive_predictions)),
        "negative_precision": _ratio(len(negative_correct), len(negative_predictions)),
        "positive_recall": positive_recall,
        "negative_recall": negative_recall,
        "forecast_positive_count": len(positive_predictions),
        "forecast_negative_count": len(negative_predictions),
        "actual_positive_count": len(actual_positive),
        "actual_negative_count": len(actual_negative),
        "is_sample_sufficient": sample_sufficient,
        "is_directionally_eligible": directionally_eligible,
    }


def _global_metrics(rows: tuple[dict[str, Any], ...], min_sample_count: int) -> dict[str, Any]:
    return _directional_group_metrics(rows, {}, tuple(), min_sample_count)


def _merge_claim_boundary() -> dict[str, bool]:
    boundary = dict(CLAIM_BOUNDARY)
    for key in ("actual_data_required", "no_live_data", "no_provider_api_calls", "no_training", "no_inference"):
        boundary[key] = bool(FORECAST_ACTUAL_CLAIM_BOUNDARY[key])
    return boundary


def build_performance_attribution(
    rows: tuple[dict, ...],
    group_fields: tuple[str, ...] = ("ticker", "timeframe", "horizon_steps", "model_family"),
    min_sample_count: int = 30,
) -> dict:
    """Build slice-level directional diagnostic attribution from local realized rows."""

    if min_sample_count <= 0:
        raise ValueError("min_sample_count must be positive")
    if not group_fields:
        raise ValueError("group_fields must not be empty")

    normalized_rows = tuple(validate_forecast_actual_row(row) for row in rows)
    grouped: dict[str, list[dict[str, Any]]] = {}
    group_keys: dict[str, dict[str, str]] = {}
    for row in normalized_rows:
        key = _group_key(row, group_fields)
        key_id = _group_key_id(key, group_fields)
        grouped.setdefault(key_id, []).append(row)
        group_keys[key_id] = key

    groups = [
        _directional_group_metrics(tuple(group_rows), group_keys[key_id], group_fields, min_sample_count)
        for key_id, group_rows in sorted(grouped.items())
    ]
    weak_groups = [
        group
        for group in groups
        if group["is_sample_sufficient"]
        and group["balanced_directional_accuracy"] is not None
        and group["balanced_directional_accuracy"] < WEAK_BALANCED_ACCURACY
    ]
    strong_groups = [
        group
        for group in groups
        if group["is_sample_sufficient"]
        and group["balanced_directional_accuracy"] is not None
        and group["balanced_directional_accuracy"] >= STRONG_BALANCED_ACCURACY
    ]

    warning_counts = Counter()
    for group in groups:
        if not group["is_sample_sufficient"]:
            warning_counts["insufficient_sample_group"] += 1
        if group["balanced_directional_accuracy"] is None:
            warning_counts["balanced_accuracy_unavailable_group"] += 1

    eligible_directional_rows = len(
        [row for row in normalized_rows if row["forecast_diagnostic"] in DIRECTIONAL_DIAGNOSTICS]
    )
    return {
        "rows_total": len(normalized_rows),
        "eligible_directional_rows": eligible_directional_rows,
        "global_metrics": _global_metrics(normalized_rows, min_sample_count),
        "group_fields": tuple(group_fields),
        "groups": groups,
        "weak_groups": weak_groups,
        "strong_groups": strong_groups,
        "warnings": dict(sorted(warning_counts.items())),
        "claim_boundary": _merge_claim_boundary(),
        "non_claim": NON_CLAIM_TEXT,
    }
