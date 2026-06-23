"""Final untouched holdout evaluation for fixed diagnostic policies."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    DOWN,
    UP,
    evaluate_forecast_accuracy,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)


CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_tuning_on_holdout": True,
    "fixed_policy_required": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Final holdout evaluator scores a fixed diagnostic policy on local holdout rows only."


def _sort_key(row: dict) -> tuple[str, str]:
    return str(row.get("forecast_timestamp") or row.get("timestamp") or row.get("source_index") or ""), str(row.get("ticker") or "")


def _group_key(row: dict) -> tuple[str, str]:
    return str(row.get("ticker") or "unspecified"), str(row.get("horizon") or "unspecified")


def build_final_holdout_split(rows: list[dict], *, holdout_fraction: float = 0.20) -> dict:
    """Split latest rows per ticker/horizon into final holdout."""

    if not 0 < holdout_fraction < 1:
        raise ValueError("holdout_fraction must be between 0 and 1")
    normalized = normalize_forecast_actual_rows(rows)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in normalized:
        grouped[_group_key(row)].append(row)
    train_validation_rows: list[dict] = []
    holdout_rows: list[dict] = []
    summaries = []
    for group, group_rows in sorted(grouped.items()):
        ordered = sorted(group_rows, key=_sort_key)
        holdout_count = max(1, int(round(len(ordered) * holdout_fraction))) if len(ordered) > 1 else len(ordered)
        holdout_count = min(holdout_count, len(ordered))
        split_index = len(ordered) - holdout_count
        group_train = ordered[:split_index]
        group_holdout = ordered[split_index:]
        train_validation_rows.extend(dict(row.get("raw") or row) for row in group_train)
        holdout_rows.extend(dict(row.get("raw") or row) for row in group_holdout)
        summaries.append(
            {
                "group": "|".join(group),
                "input_rows": len(ordered),
                "train_validation_rows": len(group_train),
                "holdout_rows": len(group_holdout),
            }
        )
    return {
        "split_status": "ready" if holdout_rows else "not_ready_no_holdout_rows",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "holdout_fraction": holdout_fraction,
        "train_validation_rows": train_validation_rows,
        "holdout_rows": holdout_rows,
        "train_validation_row_count": len(train_validation_rows),
        "holdout_row_count": len(holdout_rows),
        "group_summaries": summaries,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _flip_direction(direction: Any) -> Any:
    if direction == UP:
        return DOWN
    if direction == DOWN:
        return UP
    return direction


def _apply_policy(rows: list[dict], selected_policy: dict) -> list[dict]:
    flip = bool(selected_policy.get("flip_predictions"))
    confidence_threshold = selected_policy.get("confidence_threshold")
    model_ids = {str(item) for item in selected_policy.get("model_ids", [])}
    horizons = {str(item) for item in selected_policy.get("horizons", [])}
    tickers = {str(item).upper() for item in selected_policy.get("tickers", [])}
    output = []
    for row in normalize_forecast_actual_rows(rows):
        if model_ids and str(row.get("model_id")) not in model_ids:
            continue
        if horizons and str(row.get("horizon")) not in horizons:
            continue
        if tickers and str(row.get("ticker")).upper() not in tickers:
            continue
        probability = row.get("predicted_probability")
        if isinstance(confidence_threshold, (int, float)):
            if not isinstance(probability, (int, float)):
                continue
            confidence = max(float(probability), 1.0 - float(probability))
            if confidence < float(confidence_threshold):
                continue
        item = dict(row.get("raw") or row)
        direction = row.get("predicted_direction")
        item["predicted_direction"] = _flip_direction(direction) if flip else direction
        if flip and isinstance(probability, (int, float)):
            item["predicted_probability"] = round(1.0 - float(probability), 12)
        item["fixed_policy_id"] = selected_policy.get("policy_id", "fixed_diagnostic_policy")
        item["holdout_scoring_policy"] = {
            "flip_predictions": flip,
            "confidence_threshold": confidence_threshold,
            "model_filter_count": len(model_ids),
            "horizon_filter_count": len(horizons),
            "ticker_filter_count": len(tickers),
        }
        output.append(item)
    return output


def _group_summary(groups: dict[str, dict]) -> dict[str, dict]:
    output = {}
    for key, value in groups.items():
        directional = value.get("directional") or {}
        output[key] = {
            "rows": directional.get("sample_count"),
            "coverage_count": directional.get("coverage_count"),
            "accuracy": directional.get("accuracy"),
            "balanced_accuracy": directional.get("balanced_accuracy"),
            "mcc": directional.get("mcc"),
        }
    return output


def evaluate_final_holdout(rows: list[dict], selected_policy: dict) -> dict:
    """Evaluate a fixed selected policy on final local holdout rows."""

    if selected_policy.get("rows_are_holdout"):
        split = {
            "split_status": "ready" if rows else "not_ready_no_holdout_rows",
            "train_validation_row_count": 0,
            "holdout_row_count": len(rows),
            "holdout_rows": rows,
            "group_summaries": [],
        }
    else:
        split = build_final_holdout_split(rows, holdout_fraction=float(selected_policy.get("holdout_fraction", 0.20)))
    holdout_rows = list(split.get("holdout_rows") or [])
    scored_rows = _apply_policy(holdout_rows, selected_policy)
    accuracy = evaluate_forecast_accuracy(scored_rows)
    directional = accuracy["global"]["directional"]
    baseline = accuracy.get("baseline_comparison") or {}
    bacc = directional.get("balanced_accuracy")
    random_baseline = baseline.get("random_50_50_baseline_accuracy")
    majority = baseline.get("majority_class_baseline_accuracy")
    previous = baseline.get("previous_direction_baseline_accuracy")
    coverage = (directional.get("coverage_count") or 0) / len(holdout_rows) if holdout_rows else 0.0
    return {
        "holdout_status": "evaluated" if scored_rows else "not_ready_no_scored_holdout_rows",
        "selected_policy": selected_policy,
        "split": {key: value for key, value in split.items() if key not in {"train_validation_rows", "holdout_rows"}},
        "holdout_rows": len(holdout_rows),
        "scored_holdout_rows": len(scored_rows),
        "coverage": round(coverage, 6),
        "global_accuracy": directional.get("accuracy"),
        "global_balanced_accuracy": bacc,
        "mcc": directional.get("mcc"),
        "wilson_accuracy_interval": directional.get("wilson_accuracy_interval"),
        "confusion_matrix": directional.get("confusion_matrix"),
        "by_horizon": _group_summary((accuracy.get("groups") or {}).get("by_horizon", {})),
        "by_ticker": _group_summary((accuracy.get("groups") or {}).get("by_ticker", {})),
        "baseline_comparison": baseline,
        "beats_random": isinstance(bacc, (int, float)) and isinstance(random_baseline, (int, float)) and bacc > random_baseline,
        "beats_majority": isinstance(bacc, (int, float)) and isinstance(majority, (int, float)) and bacc > majority,
        "beats_previous_direction": isinstance(bacc, (int, float)) and isinstance(previous, (int, float)) and bacc > previous,
        "scored_rows": scored_rows,
        "accuracy_evaluation": accuracy,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_final_holdout_report(result: dict) -> str:
    """Render compact final holdout metrics."""

    baseline = result.get("baseline_comparison") or {}
    lines = [
        "# Final Holdout Evaluation",
        "",
        f"Holdout status: {result.get('holdout_status')}",
        f"Holdout rows: {result.get('holdout_rows')}",
        f"Scored holdout rows: {result.get('scored_holdout_rows')}",
        f"Coverage: {result.get('coverage')}",
        f"Global accuracy: {result.get('global_accuracy')}",
        f"Global balanced accuracy: {result.get('global_balanced_accuracy')}",
        f"MCC: {result.get('mcc')}",
        f"Wilson interval: {result.get('wilson_accuracy_interval')}",
        "",
        "Baselines:",
        f"- random 50/50: {baseline.get('random_50_50_baseline_accuracy')}",
        f"- majority class: {baseline.get('majority_class_baseline_accuracy')}",
        f"- previous direction: {baseline.get('previous_direction_baseline_accuracy')}",
        "",
        "Baseline comparisons:",
        f"- beats random: {result.get('beats_random')}",
        f"- beats majority: {result.get('beats_majority')}",
        f"- beats previous direction: {result.get('beats_previous_direction')}",
        "",
        "Boundary:",
        "The selected policy is fixed before this holdout scoring step.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a fixed policy on final local holdout rows.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--flip-predictions", action="store_true")
    parser.add_argument("--confidence-threshold", type=float, default=None)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = load_forecast_accuracy_rows(args.input)
    policy = {
        "policy_id": "cli_fixed_holdout_policy",
        "rows_are_holdout": True,
        "flip_predictions": args.flip_predictions,
        "confidence_threshold": args.confidence_threshold,
    }
    result = evaluate_final_holdout(rows, policy)
    public_result = {key: value for key, value in result.items() if key not in {"scored_rows", "accuracy_evaluation"}}
    if args.format == "report":
        print(render_final_holdout_report(public_result), end="")
    else:
        print(json.dumps(public_result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
