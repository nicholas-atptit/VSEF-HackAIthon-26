"""Safe threshold-policy tuner for eligible local model/horizon rows."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    DOWN,
    UP,
    evaluate_forecast_accuracy,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)


THRESHOLD_CANDIDATES = tuple(round(0.45 + index * 0.01, 2) for index in range(11))
MIN_GROUP_ROWS = 8
MIN_TRAIN_ROWS = 4
MIN_VALIDATION_ROWS = 2
CLAIM_BOUNDARY = {
    "policy_threshold_tuning_only": True,
    "writes_files_by_default": False,
    "explicit_temp_output_required": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_model_training": True,
    "no_model_update": True,
    "no_market_action_output": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Threshold tuning is validation-only over local labeled rows; it is not a model update."


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


def _ordered_temporal_rows(rows: tuple[dict, ...]) -> tuple[dict, ...] | None:
    parsed = [(_parse_time(row.get("forecast_timestamp")), index, row) for index, row in enumerate(rows)]
    if not parsed or any(item[0] is None for item in parsed):
        return None
    if len({item[0] for item in parsed}) < 2:
        return None
    return tuple(row for _, _, row in sorted(parsed, key=lambda item: (item[0], item[1])))


def temporal_train_validation_split(rows: list[dict], *, validation_fraction: float = 0.3) -> dict:
    """Split local rows chronologically without shuffling."""

    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    normalized = normalize_forecast_actual_rows(rows)
    ordered = _ordered_temporal_rows(normalized)
    if ordered is None:
        return {
            "split_status": "temporal_split_unavailable",
            "train_rows": [],
            "validation_rows": [],
            "row_count": len(normalized),
            "warnings": ["forecast_timestamp_not_temporal_for_all_rows"],
        }
    validation_count = max(1, int(round(len(ordered) * validation_fraction)))
    validation_count = min(validation_count, len(ordered) - 1) if len(ordered) > 1 else 0
    split_index = len(ordered) - validation_count
    return {
        "split_status": "temporal_split_ready" if validation_count else "temporal_split_unavailable",
        "train_rows": list(ordered[:split_index]),
        "validation_rows": list(ordered[split_index:]),
        "row_count": len(ordered),
        "warnings": [] if validation_count else ["validation_partition_empty"],
    }


def _rows_with_threshold(rows: list[dict], threshold: float) -> list[dict]:
    tuned_rows: list[dict[str, Any]] = []
    for row in rows:
        output = dict(row)
        probability = row.get("predicted_probability")
        if probability is None:
            tuned_rows.append(output)
            continue
        output["predicted_direction"] = UP if float(probability) >= threshold else DOWN
        output["policy_threshold"] = threshold
        tuned_rows.append(output)
    return tuned_rows


def _directional_metric(result: dict, metric: str) -> float | None:
    directional = (result.get("global") or {}).get("directional", {})
    if metric == "f1":
        values = [directional.get("f1_up"), directional.get("f1_down")]
        values = [float(value) for value in values if isinstance(value, (int, float))]
        return round(sum(values) / len(values), 6) if values else None
    value = directional.get(metric)
    return float(value) if isinstance(value, (int, float)) else None


def _metric_bundle(rows: list[dict], threshold: float) -> dict:
    result = evaluate_forecast_accuracy(_rows_with_threshold(rows, threshold))
    directional = result["global"]["directional"]
    baseline = result["baseline_comparison"]
    return {
        "threshold": threshold,
        "accuracy": directional["accuracy"],
        "balanced_accuracy": directional["balanced_accuracy"],
        "f1": _directional_metric(result, "f1"),
        "mcc": directional["mcc"],
        "coverage_count": directional["coverage_count"],
        "sample_count": directional["sample_count"],
        "baseline_comparison": baseline,
    }


def _eligible_for_threshold_tuning(rows: tuple[dict, ...]) -> tuple[bool, str | None]:
    if len(rows) < MIN_GROUP_ROWS:
        return False, "insufficient_rows_for_model_horizon"
    if not all(row.get("predicted_probability") is not None for row in rows):
        return False, "missing_probability_scores"
    if len({row.get("actual_direction") for row in rows}) < 2:
        return False, "actual_direction_class_coverage_missing"
    if _ordered_temporal_rows(rows) is None:
        return False, "temporal_split_unavailable"
    return True, None


def tune_threshold_for_model(rows: list[dict], *, metric: str = "balanced_accuracy") -> dict:
    """Tune one model/horizon probability threshold using train data and report validation metrics."""

    normalized = normalize_forecast_actual_rows(rows)
    eligible, reason = _eligible_for_threshold_tuning(normalized)
    if not eligible:
        return {
            "tuning_status": "skipped",
            "skip_reason": reason,
            "sample_count": len(normalized),
            "training_ran": False,
            "tuning_ran": False,
            "human_review_required": True,
        }
    split = temporal_train_validation_split(list(normalized))
    train_rows = split["train_rows"]
    validation_rows = split["validation_rows"]
    if len(train_rows) < MIN_TRAIN_ROWS or len(validation_rows) < MIN_VALIDATION_ROWS:
        return {
            "tuning_status": "skipped",
            "skip_reason": "temporal_split_partitions_too_small",
            "sample_count": len(normalized),
            "training_ran": False,
            "tuning_ran": False,
            "human_review_required": True,
        }
    candidates = []
    for threshold in THRESHOLD_CANDIDATES:
        train_metrics = _metric_bundle(train_rows, threshold)
        objective_value = train_metrics.get(metric)
        candidates.append(
            {
                "threshold": threshold,
                "train_metrics": train_metrics,
                "objective_value": objective_value,
            }
        )
    selectable = [candidate for candidate in candidates if isinstance(candidate.get("objective_value"), (int, float))]
    if not selectable:
        return {
            "tuning_status": "skipped",
            "skip_reason": "objective_metric_unavailable_on_train_split",
            "sample_count": len(normalized),
            "training_ran": False,
            "tuning_ran": False,
            "human_review_required": True,
        }
    selectable.sort(key=lambda item: (item["objective_value"], -abs(float(item["threshold"]) - 0.5)), reverse=True)
    selected_threshold = float(selectable[0]["threshold"])
    pre_tune = _metric_bundle(validation_rows, 0.5)
    post_tune = _metric_bundle(validation_rows, selected_threshold)
    pre_value = pre_tune.get(metric)
    post_value = post_tune.get(metric)
    improvement = None
    if isinstance(pre_value, (int, float)) and isinstance(post_value, (int, float)):
        improvement = round(float(post_value) - float(pre_value), 6)
    return {
        "tuning_status": "tuned",
        "metric": metric,
        "sample_count": len(normalized),
        "train_sample_count": len(train_rows),
        "validation_sample_count": len(validation_rows),
        "selected_threshold": selected_threshold,
        "pre_tune_validation": pre_tune,
        "post_tune_validation": post_tune,
        "validation_improvement": improvement,
        "candidate_count": len(candidates),
        "training_ran": False,
        "tuning_ran": True,
        "split_status": split["split_status"],
        "warnings": split["warnings"],
        "human_review_required": True,
    }


def _group_key(row: dict) -> tuple[str, str]:
    return str(row.get("model_id") or "unspecified"), str(row.get("horizon") or "unspecified")


def tune_all_eligible_models(rows: list[dict]) -> dict:
    """Tune every eligible model/horizon group and skip the rest with explicit reasons."""

    normalized = normalize_forecast_actual_rows(rows)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in normalized:
        groups[_group_key(row)].append(row)
    tuned_results = []
    skipped_results = []
    for (model_id, horizon), group_rows in sorted(groups.items()):
        result = tune_threshold_for_model(group_rows)
        item = {
            "model_id": model_id,
            "horizon": horizon,
            **result,
        }
        if result["tuning_status"] == "tuned":
            tuned_results.append(item)
        else:
            skipped_results.append(item)
    status = "completed" if tuned_results else "no_eligible_models"
    return {
        "tuning_status": status,
        "input_row_count": len(rows),
        "normalized_row_count": len(normalized),
        "eligible_model_count": len(tuned_results),
        "skipped_model_count": len(skipped_results),
        "tuned_models": tuned_results,
        "skipped_models": skipped_results,
        "training_ran": False,
        "tuning_ran": bool(tuned_results),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_eligible_model_tuning_report(result: dict) -> str:
    """Render a compact tuning result report."""

    tuned_lines = [
        "- {model_id}/h{horizon}: threshold={threshold}, pre_bacc={pre}, post_bacc={post}".format(
            model_id=item.get("model_id"),
            horizon=item.get("horizon"),
            threshold=item.get("selected_threshold"),
            pre=(item.get("pre_tune_validation") or {}).get("balanced_accuracy"),
            post=(item.get("post_tune_validation") or {}).get("balanced_accuracy"),
        )
        for item in result.get("tuned_models", [])
    ] or ["- none"]
    skipped_lines = [
        f"- {item.get('model_id')}/h{item.get('horizon')}: {item.get('skip_reason')}"
        for item in result.get("skipped_models", [])
    ] or ["- none"]
    lines = [
        "# Eligible Model Policy Tuning",
        "",
        f"Tuning status: {result.get('tuning_status')}",
        f"Eligible model count: {result.get('eligible_model_count')}",
        f"Skipped model count: {result.get('skipped_model_count')}",
        f"Training ran: {result.get('training_ran')}",
        f"Tuning ran: {result.get('tuning_ran')}",
        "",
        "Tuned model/horizon groups:",
        *tuned_lines,
        "",
        "Skipped model/horizon groups:",
        *skipped_lines,
        "",
        "Boundary:",
        "Only probability-threshold policy search is performed, and only with explicit local rows.",
        "Validation metrics are reported from the temporal validation partition.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _validate_output_path(path: str) -> Path:
    output = Path(path)
    parts = [part.lower() for part in output.parts]
    allowed_temp_roots = (".tmp_tuning", ".tmp_full_model_run")
    if not any(part.startswith(allowed_temp_roots) for part in parts):
        raise ValueError("write-report path must be inside .tmp_tuning* or .tmp_full_model_run")
    return output


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tune eligible local model/horizon threshold policies.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--write-report", required=True)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        output_path = _validate_output_path(args.write_report)
        rows = load_forecast_accuracy_rows(args.input)
        result = tune_all_eligible_models(rows)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    if args.format == "report":
        print(render_eligible_model_tuning_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
