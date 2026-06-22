"""Release gate for local forecast-vs-actual tuning eligibility."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    BINARY_DIRECTIONS,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)


MIN_GLOBAL_LABELED_ROWS = 12
MIN_GROUP_LABELED_ROWS = 6
MIN_DISTINCT_TIMESTAMPS = 4
LEAKAGE_NAME_TOKENS = ("actual", "realized", "future", "target", "y_true")
CLAIM_BOUNDARY = {
    "local_labeled_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training_by_default": True,
    "no_model_update": True,
    "no_market_action_output": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Release tuning gate only; tuning requires local labeled rows and temporal validation."
VALID_STATUSES = {
    "not_ready_no_labeled_data",
    "not_ready_insufficient_rows",
    "ready_for_policy_threshold_tuning",
    "ready_for_model_hyperparameter_tuning",
    "ready_for_release_evaluation_only",
}


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.startswith("row_index_"):
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _feature_columns(rows: tuple[dict, ...]) -> tuple[str, ...]:
    columns: set[str] = set()
    for row in rows:
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        if isinstance(raw.get("features"), dict):
            columns.update(f"features.{key}" for key in raw["features"])
        for key in raw:
            lowered = str(key).lower()
            if lowered in {"feature_set", "feature_family", "feature_name"}:
                continue
            if lowered.startswith("feature_") or lowered.startswith("x_"):
                columns.add(str(key))
    return tuple(sorted(columns))


def _leakage_columns(columns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        column
        for column in columns
        if any(token in column.lower() for token in LEAKAGE_NAME_TOKENS)
    )


def _duplicate_keys(rows: tuple[dict, ...]) -> list[str]:
    counts = Counter(
        (row["forecast_timestamp"], row["model_id"], row["ticker"], row["horizon"])
        for row in rows
    )
    return [
        "|".join(str(part) for part in key)
        for key, count in counts.items()
        if count > 1
    ]


def _group_counts(rows: tuple[dict, ...]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.get("actual_direction") in BINARY_DIRECTIONS:
            counts[f"model_id={row['model_id']}|horizon={row['horizon']}"] += 1
    return dict(sorted(counts.items()))


def _has_probability_scores(rows: tuple[dict, ...]) -> bool:
    return any(row.get("predicted_probability") is not None for row in rows)


def _temporal_split_possible(rows: tuple[dict, ...]) -> bool:
    parsed = [_parse_time(row.get("forecast_timestamp")) for row in rows]
    parsed = [value for value in parsed if value is not None]
    if len(set(parsed)) < MIN_DISTINCT_TIMESTAMPS:
        return False
    ordered = sorted(parsed)
    split_index = int(len(ordered) * 0.7)
    return split_index > 0 and split_index < len(ordered)


def inspect_tuning_eligibility(rows: list[dict]) -> dict:
    """Inspect release tuning eligibility without tuning or writing output."""

    normalized = normalize_forecast_actual_rows(rows)
    labeled_rows = tuple(row for row in normalized if row.get("actual_direction") in BINARY_DIRECTIONS)
    group_counts = _group_counts(labeled_rows)
    eligible_groups = {
        key: count for key, count in group_counts.items() if count >= MIN_GROUP_LABELED_ROWS
    }
    feature_columns = _feature_columns(normalized)
    leakage_columns = _leakage_columns(feature_columns)
    duplicate_keys = _duplicate_keys(normalized)
    temporal_ready = _temporal_split_possible(labeled_rows)
    score_ready = _has_probability_scores(labeled_rows)
    checks = {
        "enough_labeled_rows_globally": len(labeled_rows) >= MIN_GLOBAL_LABELED_ROWS,
        "enough_labeled_rows_by_model_horizon": bool(eligible_groups),
        "temporal_split_possible": temporal_ready,
        "no_leakage_columns_detected": not leakage_columns,
        "feature_columns_available": bool(feature_columns),
        "prediction_actual_alignment_available": bool(labeled_rows),
        "no_duplicate_timestamp_model_ticker_horizon_collisions": not duplicate_keys,
        "probability_scores_available": score_ready,
        "explicit_output_path_required": True,
        "human_review_required": True,
    }
    skip_reasons: list[str] = []
    if not labeled_rows:
        skip_reasons.append("missing_labeled_forecast_actual_rows")
    if labeled_rows and len(labeled_rows) < MIN_GLOBAL_LABELED_ROWS:
        skip_reasons.append("insufficient_global_labeled_rows")
    if labeled_rows and not eligible_groups:
        skip_reasons.append("insufficient_rows_by_model_horizon")
    if labeled_rows and not temporal_ready:
        skip_reasons.append("temporal_split_not_available")
    if leakage_columns:
        skip_reasons.append("leakage_columns_require_review")
    if duplicate_keys:
        skip_reasons.append("duplicate_forecast_identity_collisions")
    if labeled_rows and not score_ready:
        skip_reasons.append("probability_scores_missing_for_threshold_tuning")
    return {
        "eligibility_status": "inspected",
        "input_row_count": len(rows),
        "normalized_row_count": len(normalized),
        "labeled_row_count": len(labeled_rows),
        "group_counts": group_counts,
        "eligible_model_horizon_groups": eligible_groups,
        "feature_columns": list(feature_columns),
        "leakage_columns": list(leakage_columns),
        "duplicate_collision_keys": duplicate_keys[:25],
        "checks": checks,
        "skip_reasons": sorted(set(skip_reasons)),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def run_release_model_tuning_gate(rows: list[dict]) -> dict:
    """Classify release tuning readiness from local rows."""

    eligibility = inspect_tuning_eligibility(rows)
    checks = eligibility["checks"]
    labeled_count = int(eligibility["labeled_row_count"])
    if labeled_count == 0:
        status = "not_ready_no_labeled_data"
    elif not checks["enough_labeled_rows_globally"] or not checks["enough_labeled_rows_by_model_horizon"]:
        status = "not_ready_insufficient_rows"
    elif not checks["temporal_split_possible"] or not checks["no_duplicate_timestamp_model_ticker_horizon_collisions"]:
        status = "not_ready_insufficient_rows"
    elif checks["feature_columns_available"] and checks["no_leakage_columns_detected"]:
        status = "ready_for_model_hyperparameter_tuning"
    elif checks["probability_scores_available"]:
        status = "ready_for_policy_threshold_tuning"
    else:
        status = "ready_for_release_evaluation_only"
    if status not in VALID_STATUSES:
        raise AssertionError(f"unexpected release tuning status: {status}")
    return {
        "tuning_gate_status": status,
        "eligibility": eligibility,
        "allowed_tuning_scope": (
            "policy_threshold_only"
            if status == "ready_for_policy_threshold_tuning"
            else "model_hyperparameter_with_feature_matrix"
            if status == "ready_for_model_hyperparameter_tuning"
            else "evaluation_only"
        ),
        "training_ran": False,
        "tuning_ran": False,
        "human_review_required": True,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_release_model_tuning_gate_report(result: dict) -> str:
    """Render a compact release tuning gate report."""

    eligibility = result.get("eligibility") or {}
    skip_lines = [f"- {item}" for item in eligibility.get("skip_reasons", [])] or ["- none"]
    group_lines = [
        f"- {key}: {count}"
        for key, count in (eligibility.get("eligible_model_horizon_groups") or {}).items()
    ] or ["- none"]
    lines = [
        "# Release Model Tuning Gate",
        "",
        f"Tuning gate status: {result.get('tuning_gate_status')}",
        f"Labeled rows: {eligibility.get('labeled_row_count')}",
        f"Allowed scope: {result.get('allowed_tuning_scope')}",
        f"Training ran: {result.get('training_ran')}",
        f"Tuning ran: {result.get('tuning_ran')}",
        "",
        "Eligible model/horizon groups:",
        *group_lines,
        "",
        "Skip reasons:",
        *skip_lines,
        "",
        "Boundary:",
        "No model training or model update is run by this gate.",
        "Any tuning output requires an explicit temporary output path and human review.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect release tuning eligibility for explicit local rows.")
    parser.add_argument("--input", default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        rows = load_forecast_accuracy_rows(args.input) if args.input else []
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    result = run_release_model_tuning_gate(rows)
    if args.format == "report":
        print(render_release_model_tuning_gate_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
