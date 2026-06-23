"""Selective local diagnostic forecast mode with abstention by robust slice."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    evaluate_forecast_accuracy,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)
from src.hackaithon_mvp.robust_forecast_slice_gate import (
    FORECAST_ALLOWED,
    MIN_ROWS_DEFAULT,
    build_forecast_allowed_slices,
)


CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_model_update": True,
    "diagnostic_forecast_retention_only": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Selective forecast mode emits diagnostic forecast retained rows only for robust local slices."


def _slice_id(row: dict[str, Any]) -> str:
    return "{ticker}|h{horizon}|{model}".format(
        ticker=row.get("ticker") or "unspecified",
        horizon=row.get("horizon") or "unspecified",
        model=row.get("model_id") or "unspecified",
    )


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("raw")
    return dict(raw) if isinstance(raw, dict) else dict(row)


def _summary_group(accuracy: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    groups = (accuracy.get("groups") or {}).get(key, {})
    output = {}
    for group_key, value in sorted(groups.items()):
        directional = value.get("directional") or {}
        output[group_key] = {
            "rows": directional.get("sample_count"),
            "coverage_count": directional.get("coverage_count"),
            "accuracy": directional.get("accuracy"),
            "balanced_accuracy": directional.get("balanced_accuracy"),
            "mcc": directional.get("mcc"),
        }
    return output


def _metric(rows: list[dict], total_rows: int) -> dict[str, Any]:
    accuracy = evaluate_forecast_accuracy(rows)
    directional = accuracy["global"]["directional"]
    baseline = accuracy.get("baseline_comparison") or {}
    retained = int(directional.get("coverage_count") or 0)
    return {
        "retained_row_count": retained,
        "abstained_rows": max(total_rows - retained, 0),
        "forecast_coverage": round(retained / total_rows, 6) if total_rows else 0.0,
        "global_retained_accuracy": directional.get("accuracy"),
        "global_retained_balanced_accuracy": directional.get("balanced_accuracy"),
        "mcc": directional.get("mcc"),
        "wilson_accuracy_interval": directional.get("wilson_accuracy_interval"),
        "baselines_on_retained_rows": {
            "random_50_50": baseline.get("random_50_50_baseline_accuracy"),
            "majority_class": baseline.get("majority_class_baseline_accuracy"),
            "previous_direction": baseline.get("previous_direction_baseline_accuracy"),
        },
        "beats_random": _beats(directional.get("balanced_accuracy"), baseline.get("random_50_50_baseline_accuracy")),
        "beats_majority": _beats(directional.get("balanced_accuracy"), baseline.get("majority_class_baseline_accuracy")),
        "beats_previous_direction": _beats(directional.get("balanced_accuracy"), baseline.get("previous_direction_baseline_accuracy")),
        "by_ticker": _summary_group(accuracy, "by_ticker"),
        "by_horizon": _summary_group(accuracy, "by_horizon"),
        "by_ticker_horizon": _summary_group(accuracy, "by_ticker_horizon"),
        "accuracy_evaluation": accuracy,
    }


def _beats(value: Any, baseline: Any) -> bool:
    return isinstance(value, (int, float)) and isinstance(baseline, (int, float)) and float(value) > float(baseline)


def build_selective_forecast_policy(rows: list[dict], *, min_rows: int = MIN_ROWS_DEFAULT) -> dict:
    """Build a policy that keeps only robust local forecast slices."""

    gate = build_forecast_allowed_slices(rows, min_rows=min_rows)
    abstention_reasons = {}
    for slice_id in gate.get("abstained_slices", []):
        item = (gate.get("slice_results") or {}).get(slice_id, {})
        abstention_reasons[slice_id] = item.get("abstention_reason") or "abstained due to insufficient evidence"
    return {
        "policy_status": "completed" if gate.get("gate_status") == "completed" else gate.get("gate_status"),
        "policy_id": "robust_selective_forecast_policy",
        "min_rows": min_rows,
        "allowed_slices": list(gate.get("allowed_slices") or []),
        "abstained_slices": list(gate.get("abstained_slices") or []),
        "allowed_slice_count": gate.get("allowed_slice_count", 0),
        "abstained_slice_count": gate.get("abstained_slice_count", 0),
        "abstention_reasons": abstention_reasons,
        "row_labels": {
            "retained": "diagnostic forecast retained",
            "abstained": "abstained due to insufficient evidence",
            "review": "human review required",
        },
        "gate": gate,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def evaluate_selective_forecast_policy(rows: list[dict], policy: dict) -> dict:
    """Evaluate retained rows from a selective policy and abstain the rest."""

    normalized = list(normalize_forecast_actual_rows(rows))
    allowed = {str(item) for item in policy.get("allowed_slices", [])}
    retained_rows: list[dict[str, Any]] = []
    abstained_rows: list[dict[str, Any]] = []
    reason_counts = Counter()
    for row in normalized:
        slice_id = _slice_id(row)
        output = _public_row(row)
        output["selective_forecast_slice_id"] = slice_id
        if slice_id in allowed:
            output["selective_forecast_status"] = "diagnostic forecast retained"
            output["human_review_required"] = True
            retained_rows.append(output)
        else:
            reason = (policy.get("abstention_reasons") or {}).get(slice_id) or "abstained due to insufficient evidence"
            output["selective_forecast_status"] = "abstained due to insufficient evidence"
            output["abstention_reason"] = reason
            output["human_review_required"] = True
            abstained_rows.append(output)
            reason_counts[reason] += 1

    metrics = _metric(retained_rows, len(normalized))
    by_slice_counts = Counter(_slice_id(row) for row in normalized)
    result = {
        "evaluation_status": "completed" if normalized else "not_ready_no_rows",
        "policy_id": policy.get("policy_id"),
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "allowed_slices": list(policy.get("allowed_slices") or []),
        "abstained_slices": list(policy.get("abstained_slices") or []),
        "allowed_slice_count": len(policy.get("allowed_slices") or []),
        "abstained_slice_count": len(policy.get("abstained_slices") or []),
        "retained_rows": retained_rows,
        "retained_row_count": len(retained_rows),
        "abstained_rows_payload": abstained_rows,
        "abstention_reasons": dict(sorted((policy.get("abstention_reasons") or {}).items())),
        "abstained_rows_by_reason": dict(reason_counts.most_common()),
        "rows_by_slice": dict(sorted(by_slice_counts.items())),
        **{key: value for key, value in metrics.items() if key != "accuracy_evaluation"},
        "accuracy_evaluation": metrics["accuracy_evaluation"],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    return result


def render_selective_forecast_mode_report(result: dict) -> str:
    """Render a compact selective forecast mode report."""

    baselines = result.get("baselines_on_retained_rows") or {}
    lines = [
        "# Selective Forecast Mode",
        "",
        f"Evaluation status: {result.get('evaluation_status')}",
        f"Input rows: {result.get('input_rows')}",
        f"Allowed slices: {result.get('allowed_slice_count')}",
        f"Abstained slices: {result.get('abstained_slice_count')}",
        f"Diagnostic forecast retained rows: {result.get('retained_rows') if isinstance(result.get('retained_rows'), int) else len(result.get('retained_rows') or [])}",
        f"Abstained rows: {result.get('abstained_rows')}",
        f"Forecast coverage: {result.get('forecast_coverage')}",
        f"Retained accuracy: {result.get('global_retained_accuracy')}",
        f"Retained balanced accuracy: {result.get('global_retained_balanced_accuracy')}",
        f"Retained MCC: {result.get('mcc')}",
        "",
        "Baselines on retained rows:",
        f"- random 50/50: {baselines.get('random_50_50')}",
        f"- majority class: {baselines.get('majority_class')}",
        f"- previous direction: {baselines.get('previous_direction')}",
        "",
        "Baseline comparisons:",
        f"- beats random: {result.get('beats_random')}",
        f"- beats majority: {result.get('beats_majority')}",
        f"- beats previous direction: {result.get('beats_previous_direction')}",
        "",
        "Abstained slices:",
    ]
    reasons = result.get("abstention_reasons") or {}
    lines.extend([f"- {slice_id}: {reason}" for slice_id, reason in list(reasons.items())[:20]] or ["- none"])
    lines.extend(
        [
            "",
            "Boundary:",
            "Rows outside allowed robust slices are abstained due to insufficient evidence; human review required.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    output = dict(result)
    retained = output.get("retained_rows")
    abstained = output.get("abstained_rows_payload")
    if isinstance(retained, list):
        output["retained_rows"] = len(retained)
    if isinstance(abstained, list):
        output["abstained_rows"] = len(abstained)
    output.pop("abstained_rows_payload", None)
    output.pop("accuracy_evaluation", None)
    return output


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate selective local diagnostic forecast mode.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--min-rows", type=int, default=MIN_ROWS_DEFAULT)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        rows = load_forecast_accuracy_rows(args.input)
        policy = build_selective_forecast_policy(rows, min_rows=args.min_rows)
        result = evaluate_selective_forecast_policy(rows, policy)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    public = _public_result(result)
    if args.format == "report":
        print(render_selective_forecast_mode_report(public), end="")
    else:
        print(json.dumps(public, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
