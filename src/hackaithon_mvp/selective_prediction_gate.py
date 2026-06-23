"""Selective diagnostic prediction retention by confidence."""

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


CONFIDENCE_THRESHOLDS = (0.50, 0.52, 0.55, 0.57, 0.60, 0.65, 0.70)
MIN_DEFAULT_COVERAGE = 0.30
CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_model_update": True,
    "diagnostic_abstention_only": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Selective prediction gate retains diagnostic rows by confidence and abstains on low-confidence rows."


def _confidence(row: dict) -> float | None:
    probability = row.get("predicted_probability")
    if not isinstance(probability, (int, float)):
        return None
    probability = min(max(float(probability), 0.0), 1.0)
    return max(probability, 1.0 - probability)


def _retained_rows(rows: tuple[dict, ...], threshold: float) -> list[dict]:
    retained = []
    for row in rows:
        confidence = _confidence(row)
        if confidence is None or confidence < threshold:
            continue
        output = dict(row.get("raw") or row)
        output["diagnostic_retention_status"] = "diagnostic_prediction_retained"
        output["confidence_threshold"] = threshold
        output["diagnostic_confidence"] = round(confidence, 6)
        retained.append(output)
    return retained


def _metric(rows: list[dict], total_count: int) -> dict:
    result = evaluate_forecast_accuracy(rows)
    directional = result["global"]["directional"]
    baseline = result.get("baseline_comparison") or {}
    retained = int(directional.get("coverage_count") or 0)
    return {
        "rows_retained": retained,
        "rows_abstained": max(total_count - retained, 0),
        "coverage": round(retained / total_count, 6) if total_count else 0.0,
        "directional_accuracy": directional.get("accuracy"),
        "balanced_accuracy": directional.get("balanced_accuracy"),
        "mcc": directional.get("mcc"),
        "baseline_comparison": {
            "majority_class": baseline.get("majority_class_baseline_accuracy"),
            "random_50_50": baseline.get("random_50_50_baseline_accuracy"),
            "previous_direction": baseline.get("previous_direction_baseline_accuracy"),
        },
    }


def _nearest_coverage_buckets(threshold_results: list[dict]) -> dict[str, dict]:
    buckets = {}
    for target in (0.50, 0.70, 0.90):
        if not threshold_results:
            buckets[f"nearest_{int(target * 100)}pct_coverage"] = {}
            continue
        buckets[f"nearest_{int(target * 100)}pct_coverage"] = min(
            threshold_results,
            key=lambda item: abs(float(item.get("coverage") or 0.0) - target),
        )
    return buckets


def evaluate_confidence_buckets(rows: list[dict]) -> dict:
    """Evaluate fixed confidence buckets over local forecast-vs-actual rows."""

    normalized = normalize_forecast_actual_rows(rows)
    probability_rows = tuple(row for row in normalized if isinstance(row.get("predicted_probability"), (int, float)))
    threshold_results = []
    for threshold in CONFIDENCE_THRESHOLDS:
        retained = _retained_rows(probability_rows, threshold)
        threshold_results.append({"confidence_threshold": threshold, **_metric(retained, len(probability_rows))})
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in probability_rows:
        confidence = _confidence(row)
        label = "unavailable" if confidence is None else "0.50-0.57" if confidence < 0.57 else "0.57-0.65" if confidence < 0.65 else "0.65+"
        grouped[label].append(dict(row.get("raw") or row))
    return {
        "evaluation_status": "completed" if probability_rows else "not_ready_no_probability_rows",
        "input_rows": len(rows),
        "probability_rows": len(probability_rows),
        "threshold_results": threshold_results,
        "coverage_buckets": _nearest_coverage_buckets(threshold_results),
        "confidence_bucket_metrics": {key: _metric(value, len(probability_rows)) for key, value in sorted(grouped.items())},
        "row_labels": {
            "retained": "diagnostic_prediction_retained",
            "abstained": "abstained_low_confidence",
            "candidate": "review_candidate",
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def tune_confidence_gate(rows: list[dict], *, metric: str = "balanced_accuracy") -> dict:
    """Select a confidence threshold on supplied validation rows only."""

    if metric not in {"balanced_accuracy", "directional_accuracy", "mcc"}:
        raise ValueError("metric must be balanced_accuracy, directional_accuracy, or mcc")
    evaluation = evaluate_confidence_buckets(rows)
    candidates = [
        item
        for item in evaluation.get("threshold_results", [])
        if float(item.get("coverage") or 0.0) >= MIN_DEFAULT_COVERAGE and isinstance(item.get(metric), (int, float))
    ]
    if not candidates:
        return {
            "tuning_status": "no_confidence_gate_selected",
            "selection_metric": metric,
            "selected_threshold": None,
            "selected_metrics": None,
            "evaluation": evaluation,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
            "human_review_required": True,
        }
    candidates.sort(
        key=lambda item: (
            float(item.get(metric) or -999.0),
            float(item.get("mcc") or -999.0),
            float(item.get("coverage") or 0.0),
        ),
        reverse=True,
    )
    selected = candidates[0]
    return {
        "tuning_status": "completed",
        "selection_metric": metric,
        "minimum_coverage": MIN_DEFAULT_COVERAGE,
        "selected_threshold": selected.get("confidence_threshold"),
        "selected_metrics": selected,
        "evaluation": evaluation,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_selective_prediction_report(result: dict) -> str:
    """Render compact selective prediction diagnostics."""

    selected = result.get("selected_metrics") if result.get("tuning_status") else None
    evaluation = result.get("evaluation") or result
    lines = [
        "# Selective Prediction Gate",
        "",
        f"Tuning status: {result.get('tuning_status', evaluation.get('evaluation_status'))}",
        f"Probability rows: {evaluation.get('probability_rows')}",
        f"Selected threshold: {result.get('selected_threshold')}",
        f"Selected balanced accuracy: {(selected or {}).get('balanced_accuracy')}",
        f"Selected accuracy: {(selected or {}).get('directional_accuracy')}",
        f"Selected coverage: {(selected or {}).get('coverage')}",
        f"Rows retained: {(selected or {}).get('rows_retained')}",
        f"Rows abstained: {(selected or {}).get('rows_abstained')}",
        "",
        "Thresholds:",
    ]
    for item in evaluation.get("threshold_results", []):
        lines.append(
            "- threshold={threshold}: coverage={coverage}, accuracy={accuracy}, balanced_accuracy={bacc}, mcc={mcc}".format(
                threshold=item.get("confidence_threshold"),
                coverage=item.get("coverage"),
                accuracy=item.get("directional_accuracy"),
                bacc=item.get("balanced_accuracy"),
                mcc=item.get("mcc"),
            )
        )
    if not evaluation.get("threshold_results"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "Low-confidence rows are abstained for human review; retained rows are diagnostic_prediction_retained.",
            str(result.get("non_claim", evaluation.get("non_claim", NON_CLAIM_TEXT))),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tune a local diagnostic confidence gate.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--metric", choices=("balanced_accuracy", "directional_accuracy", "mcc"), default="balanced_accuracy")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = load_forecast_accuracy_rows(args.input)
    result = tune_confidence_gate(rows, metric=args.metric)
    if args.format == "report":
        print(render_selective_prediction_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
