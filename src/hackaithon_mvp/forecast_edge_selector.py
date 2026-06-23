"""Select robust forecast-edge slices from clean holdout model results."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy


MIN_HOLDOUT_ROWS = 300
MIN_HOLDOUT_BALANCED_ACCURACY = 0.52
MAX_VALIDATION_HOLDOUT_GAP = 0.15
CLAIM_BOUNDARY = {
    "local_holdout_rows_only": True,
    "selection_uses_strict_gates": True,
    "coverage_disclosed": True,
    "no_market_action_output": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Forecast edge selection is local diagnostic evidence with explicit coverage."


def _metric(metrics: dict, key: str) -> float | None:
    value = metrics.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _beats(value: Any, baseline: Any) -> bool:
    return isinstance(value, (int, float)) and isinstance(baseline, (int, float)) and float(value) > float(baseline)


def _slice_id(result: dict) -> str:
    if result.get("slice_id"):
        return str(result["slice_id"])
    ticker = str(result.get("ticker") or "GLOBAL")
    horizon = str(result.get("horizon") or "unspecified")
    model_id = str(result.get("model_id") or result.get("model_key") or "model")
    return f"{ticker}|h{horizon}|{model_id}"


def _holdout_metrics(result: dict) -> dict:
    metrics = result.get("holdout_metrics") or result.get("metrics") or {}
    if "directional" in metrics:
        metrics = metrics["directional"]
    return metrics if isinstance(metrics, dict) else {}


def _validation_metrics(result: dict) -> dict:
    metrics = result.get("validation_metrics") or {}
    if "directional" in metrics:
        metrics = metrics["directional"]
    return metrics if isinstance(metrics, dict) else {}


def _reject_reasons(result: dict, *, min_holdout_rows: int) -> list[str]:
    holdout = _holdout_metrics(result)
    validation = _validation_metrics(result)
    holdout_rows = int(result.get("holdout_rows") or holdout.get("coverage_count") or 0)
    holdout_bacc = _metric(holdout, "balanced_accuracy")
    validation_bacc = _metric(validation, "balanced_accuracy")
    mcc = _metric(holdout, "mcc")
    random_baseline = result.get("random_baseline")
    majority_baseline = result.get("majority_baseline")
    if random_baseline is None:
        random_baseline = (result.get("holdout_baselines") or {}).get("random_50_50_baseline_accuracy")
    if majority_baseline is None:
        majority_baseline = (result.get("holdout_baselines") or {}).get("majority_class_baseline_accuracy")
    reasons = []
    if holdout_rows < int(min_holdout_rows):
        reasons.append("insufficient_holdout_rows")
    if holdout_bacc is None or holdout_bacc <= MIN_HOLDOUT_BALANCED_ACCURACY:
        reasons.append("holdout_balanced_accuracy_gate_failed")
    if mcc is None or mcc <= 0:
        reasons.append("mcc_gate_failed")
    if not _beats(holdout_bacc, random_baseline if random_baseline is not None else 0.5):
        reasons.append("does_not_beat_random")
    if not _beats(holdout_bacc, majority_baseline):
        reasons.append("does_not_beat_majority")
    if str(result.get("duplicate_key_severity") or "none").lower() == "high":
        reasons.append("duplicate_key_high_severity")
    if str(result.get("overlap_severity") or "none").lower() == "high":
        reasons.append("overlap_high_severity")
    if bool(result.get("leakage_warning")):
        reasons.append("leakage_warning")
    if validation_bacc is not None and holdout_bacc is not None and validation_bacc - holdout_bacc > MAX_VALIDATION_HOLDOUT_GAP:
        reasons.append("validation_holdout_gap_excessive")
    return reasons


def _best_group(groups: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    candidates = []
    for key, value in groups.items():
        directional = value.get("directional") if isinstance(value.get("directional"), dict) else value
        score = directional.get("balanced_accuracy") if isinstance(directional, dict) else None
        rows = directional.get("coverage_count", 0) if isinstance(directional, dict) else 0
        if isinstance(score, (int, float)):
            candidates.append({"slice": key, "balanced_accuracy": score, "rows": rows})
    if not candidates:
        return None
    candidates.sort(key=lambda item: (float(item["balanced_accuracy"]), int(item["rows"])), reverse=True)
    return candidates[0]


def select_forecast_edge_slices(results: list[dict]) -> dict:
    """Apply strict gates and evaluate retained holdout forecast rows."""

    allowed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    retained_rows: list[dict[str, Any]] = []
    total_holdout_rows = 0
    for result in results:
        holdout = _holdout_metrics(result)
        holdout_rows = int(result.get("holdout_rows") or holdout.get("coverage_count") or 0)
        total_holdout_rows += holdout_rows
        reasons = _reject_reasons(result, min_holdout_rows=int(result.get("minimum_holdout_rows") or MIN_HOLDOUT_ROWS))
        item = {
            "slice_id": _slice_id(result),
            "ticker": result.get("ticker"),
            "horizon": result.get("horizon"),
            "model_id": result.get("model_id") or result.get("model_key"),
            "holdout_rows": holdout_rows,
            "holdout_balanced_accuracy": holdout.get("balanced_accuracy"),
            "holdout_accuracy": holdout.get("accuracy"),
            "holdout_mcc": holdout.get("mcc"),
            "random_baseline": result.get("random_baseline")
            if result.get("random_baseline") is not None
            else (result.get("holdout_baselines") or {}).get("random_50_50_baseline_accuracy"),
            "majority_baseline": result.get("majority_baseline")
            if result.get("majority_baseline") is not None
            else (result.get("holdout_baselines") or {}).get("majority_class_baseline_accuracy"),
            "previous_direction_baseline": result.get("previous_direction_baseline")
            if result.get("previous_direction_baseline") is not None
            else (result.get("holdout_baselines") or {}).get("previous_direction_baseline_accuracy"),
        }
        if reasons:
            rejected.append({**item, "rejection_reasons": reasons})
            continue
        allowed.append({**item, "selection_status": "forecast_edge_allowed", "human_review_required": True})
        for row in result.get("holdout_forecast_rows") or []:
            retained_rows.append(dict(row))

    retained_eval = evaluate_forecast_accuracy(retained_rows)
    directional = retained_eval.get("global", {}).get("directional", {})
    baselines = retained_eval.get("baseline_comparison") or {}
    retained_rows_count = int(directional.get("coverage_count") or 0)
    retained_bacc = directional.get("balanced_accuracy")
    retained_accuracy = directional.get("accuracy")
    retained_mcc = directional.get("mcc")
    random_baseline = baselines.get("random_50_50_baseline_accuracy")
    majority_baseline = baselines.get("majority_class_baseline_accuracy")
    previous_baseline = baselines.get("previous_direction_baseline_accuracy")
    status = "forecast_edge_selected" if allowed else "no_forecast_edge_selected"
    selective_claim_allowed = bool(
        allowed and _beats(retained_bacc, random_baseline) and _beats(retained_bacc, majority_baseline)
    )
    broad_claim_allowed = bool(selective_claim_allowed and _beats(retained_bacc, previous_baseline) and retained_rows_count >= total_holdout_rows * 0.50)
    return {
        "selection_status": status,
        "allowed_slices": allowed,
        "rejected_slices": rejected,
        "allowed_slice_count": len(allowed),
        "rejected_slice_count": len(rejected),
        "total_holdout_rows": total_holdout_rows,
        "retained_holdout_rows": retained_rows_count,
        "retained_forecast_rows": retained_rows,
        "retained_coverage": round(retained_rows_count / total_holdout_rows, 6) if total_holdout_rows else 0.0,
        "retained_holdout_accuracy": retained_accuracy,
        "retained_holdout_balanced_accuracy": retained_bacc,
        "retained_holdout_mcc": retained_mcc,
        "retained_baselines": {
            "random": random_baseline,
            "majority": majority_baseline,
            "previous_direction": previous_baseline,
        },
        "beats_random": _beats(retained_bacc, random_baseline),
        "beats_majority": _beats(retained_bacc, majority_baseline),
        "beats_previous_direction": _beats(retained_bacc, previous_baseline),
        "best_ticker": _best_group(retained_eval.get("groups", {}).get("by_ticker", {})),
        "best_horizon": _best_group(retained_eval.get("groups", {}).get("by_horizon", {})),
        "best_ticker_horizon": _best_group(retained_eval.get("groups", {}).get("by_ticker_horizon", {})),
        "rejection_reason_distribution": dict(Counter(reason for item in rejected for reason in item["rejection_reasons"])),
        "accuracy_evaluation": retained_eval,
        "selective_forecast_claim_allowed": selective_claim_allowed,
        "broad_performance_claim_allowed": broad_claim_allowed,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_forecast_edge_selection_report(result: dict) -> str:
    """Render a compact forecast-edge selection report."""

    baselines = result.get("retained_baselines") or {}
    lines = [
        "# Forecast Edge Selector",
        "",
        f"Selection status: {result.get('selection_status')}",
        f"Allowed slices: {result.get('allowed_slice_count')}",
        f"Rejected slices: {result.get('rejected_slice_count')}",
        f"Retained coverage: {result.get('retained_coverage')}",
        f"Retained holdout accuracy: {result.get('retained_holdout_accuracy')}",
        f"Retained holdout balanced accuracy: {result.get('retained_holdout_balanced_accuracy')}",
        f"Retained holdout MCC: {result.get('retained_holdout_mcc')}",
        "",
        "Retained baselines:",
        f"- random: {baselines.get('random')}",
        f"- majority: {baselines.get('majority')}",
        f"- previous direction: {baselines.get('previous_direction')}",
        "",
        "Gate outcomes:",
        f"- beats random: {result.get('beats_random')}",
        f"- beats majority: {result.get('beats_majority')}",
        f"- beats previous direction: {result.get('beats_previous_direction')}",
        "",
        "Top rejection reasons:",
    ]
    reasons = result.get("rejection_reason_distribution") or {}
    lines.extend([f"- {key}: {value}" for key, value in reasons.items()] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "Allowed slices require strict local holdout gates and disclosed coverage.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select robust forecast-edge slices from model result JSON.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    results = payload.get("model_results") if isinstance(payload, dict) else payload
    if not isinstance(results, list):
        raise SystemExit("input must be a list or object with model_results")
    result = select_forecast_edge_slices(results)
    if args.format == "report":
        print(render_forecast_edge_selection_report({key: value for key, value in result.items() if key != "retained_forecast_rows"}), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
