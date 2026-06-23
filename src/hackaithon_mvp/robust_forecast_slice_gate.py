"""Robust local slice gate for selective diagnostic forecasts."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    DOWN,
    UP,
    evaluate_forecast_accuracy,
    load_forecast_accuracy_rows,
    normalize_forecast_actual_rows,
)
from src.hackaithon_mvp.forecast_data_repair_audit import audit_forecast_dataset_integrity
from src.hackaithon_mvp.fresh_validation_protocol import build_three_way_time_split


FORECAST_ALLOWED = "forecast_allowed"
ABSTAIN_INSUFFICIENT_ROWS = "abstain_insufficient_rows"
ABSTAIN_BELOW_RANDOM = "abstain_below_random"
ABSTAIN_BELOW_MAJORITY = "abstain_below_majority"
ABSTAIN_LEAKAGE_RISK = "abstain_leakage_risk"
ABSTAIN_UNSTABLE_GAP = "abstain_unstable_validation_holdout_gap"
DIAGNOSTIC_PREVIOUS_DOMINATES = "diagnostic_only_previous_baseline_dominates"
MIN_ROWS_DEFAULT = 300
MIN_BALANCED_ACCURACY = 0.52
MAX_VALIDATION_HOLDOUT_GAP = 0.15
MAX_OVERLAP_RATE = 0.05
CLAIM_BOUNDARY = {
    "local_rows_required": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_model_update": True,
    "strict_abstention_gate": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Robust forecast slice gate allows only local diagnostic slices that pass out-of-sample checks."
BINARY_DIRECTIONS = {UP, DOWN}


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _slice_id(row: dict[str, Any]) -> str:
    return "{ticker}|h{horizon}|{model}".format(
        ticker=row.get("ticker") or "unspecified",
        horizon=row.get("horizon") or "unspecified",
        model=row.get("model_id") or "unspecified",
    )


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("raw")
    return dict(raw) if isinstance(raw, dict) else dict(row)


def _metric(rows: list[dict]) -> dict[str, Any]:
    accuracy = evaluate_forecast_accuracy(rows)
    directional = accuracy["global"]["directional"]
    baseline = accuracy.get("baseline_comparison") or {}
    return {
        "rows": len(rows),
        "coverage_count": directional.get("coverage_count"),
        "accuracy": directional.get("accuracy"),
        "balanced_accuracy": directional.get("balanced_accuracy"),
        "mcc": directional.get("mcc"),
        "wilson_accuracy_interval": directional.get("wilson_accuracy_interval"),
        "random_baseline": baseline.get("random_50_50_baseline_accuracy"),
        "majority_baseline": baseline.get("majority_class_baseline_accuracy"),
        "previous_direction_baseline": baseline.get("previous_direction_baseline_accuracy"),
    }


def _wilson_lower(metric: dict[str, Any]) -> float | None:
    interval = metric.get("wilson_accuracy_interval")
    if isinstance(interval, dict):
        value = interval.get("lower")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _max_overlap_rate(audit: dict[str, Any]) -> float:
    overlap = audit.get("overlapping_label_windows") or {}
    rates = [
        float(item.get("overlap_rate") or 0.0)
        for item in (overlap.get("overlap_rate_by_horizon") or {}).values()
        if isinstance(item, dict)
    ]
    return max(rates or [float(overlap.get("overlap_rate") or 0.0)])


def _beats(value: Any, baseline: Any) -> bool:
    return isinstance(value, (int, float)) and isinstance(baseline, (int, float)) and float(value) > float(baseline)


def _status_for_slice(
    *,
    row_count: int,
    audit: dict[str, Any],
    validation_metric: dict[str, Any],
    holdout_metric: dict[str, Any],
    min_rows: int,
    previous_baseline_leakage_risk: bool,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if row_count < min_rows:
        reasons.append("minimum rows not met")
        return ABSTAIN_INSUFFICIENT_ROWS, reasons

    duplicate = (audit.get("duplicate_prediction_keys") or {}).get("duplicate_key_severity")
    leakage_warning = bool(audit.get("leakage_warning"))
    overlap_rate = _max_overlap_rate(audit)
    if duplicate == "high" or leakage_warning or overlap_rate > MAX_OVERLAP_RATE:
        if duplicate == "high":
            reasons.append("duplicate-key severity is high")
        if leakage_warning:
            reasons.append("leakage warning present")
        if overlap_rate > MAX_OVERLAP_RATE:
            reasons.append("overlap rate exceeds gate")
        return ABSTAIN_LEAKAGE_RISK, reasons

    validation_bacc = validation_metric.get("balanced_accuracy")
    holdout_bacc = holdout_metric.get("balanced_accuracy")
    if not isinstance(validation_bacc, (int, float)) or not isinstance(holdout_bacc, (int, float)):
        reasons.append("balanced accuracy unavailable")
        return ABSTAIN_BELOW_RANDOM, reasons
    if validation_bacc <= MIN_BALANCED_ACCURACY or holdout_bacc <= MIN_BALANCED_ACCURACY:
        reasons.append("validation or holdout balanced accuracy does not clear 0.52")
        random_baseline = holdout_metric.get("random_baseline")
        if isinstance(random_baseline, (int, float)) and holdout_bacc <= random_baseline:
            return ABSTAIN_BELOW_RANDOM, reasons
        return ABSTAIN_UNSTABLE_GAP, reasons
    if abs(float(validation_bacc) - float(holdout_bacc)) > MAX_VALIDATION_HOLDOUT_GAP:
        reasons.append("validation-to-holdout balanced accuracy gap is too large")
        return ABSTAIN_UNSTABLE_GAP, reasons

    if not _beats(holdout_bacc, holdout_metric.get("random_baseline")):
        reasons.append("holdout balanced accuracy does not beat random baseline")
        return ABSTAIN_BELOW_RANDOM, reasons
    if not _beats(holdout_bacc, holdout_metric.get("majority_baseline")):
        reasons.append("holdout balanced accuracy does not beat majority baseline")
        return ABSTAIN_BELOW_MAJORITY, reasons

    mcc = holdout_metric.get("mcc")
    if not isinstance(mcc, (int, float)) or mcc <= 0:
        reasons.append("holdout MCC is not positive")
        return ABSTAIN_BELOW_RANDOM, reasons

    wilson_lower = _wilson_lower(holdout_metric)
    if wilson_lower is not None and wilson_lower < 0.45:
        reasons.append("Wilson lower bound is weak")
        return ABSTAIN_UNSTABLE_GAP, reasons

    previous = holdout_metric.get("previous_direction_baseline")
    if (
        not previous_baseline_leakage_risk
        and isinstance(previous, (int, float))
        and isinstance(holdout_bacc, (int, float))
        and previous >= holdout_bacc
    ):
        reasons.append("previous-direction baseline dominates retained evidence")
        return DIAGNOSTIC_PREVIOUS_DOMINATES, reasons

    reasons.append("all robust gate criteria passed")
    return FORECAST_ALLOWED, reasons


def _previous_baseline_leakage_risk(rows: list[dict]) -> bool:
    normalized = normalize_forecast_actual_rows(rows)
    previous_by_group: dict[tuple[str, str, str], dict[str, Any]] = {}
    non_earlier = 0
    for row in sorted(
        normalized,
        key=lambda item: (
            str(item.get("ticker")),
            str(item.get("horizon")),
            str(item.get("model_id")),
            str(item.get("forecast_timestamp")),
            int(item.get("source_index") or 0),
        ),
    ):
        group = (str(row.get("ticker")), str(row.get("horizon")), str(row.get("model_id")))
        previous = previous_by_group.get(group)
        if previous is not None:
            prev_time = _parse_time(previous.get("forecast_timestamp"))
            current_time = _parse_time(row.get("forecast_timestamp"))
            if prev_time is not None and current_time is not None and prev_time >= current_time:
                non_earlier += 1
        previous_by_group[group] = row
    return non_earlier > 0


def evaluate_slice_stability(rows: list[dict]) -> dict:
    """Evaluate one ticker/horizon/model slice over validation and holdout rows."""

    normalized = list(normalize_forecast_actual_rows(rows))
    source_rows = [_public_row(row) for row in normalized]
    split = build_three_way_time_split(source_rows)
    validation_rows = list(split.get("validation_rows") or [])
    holdout_rows = list(split.get("holdout_rows") or [])
    if not validation_rows or not holdout_rows and normalized:
        ordered = sorted(source_rows, key=lambda row: str(row.get("forecast_timestamp") or ""))
        midpoint = max(1, len(ordered) // 2)
        validation_rows = ordered[:midpoint]
        holdout_rows = ordered[midpoint:] or ordered[:]
    validation_metric = _metric(validation_rows)
    holdout_metric = _metric(holdout_rows)
    audit = audit_forecast_dataset_integrity(source_rows)
    validation_bacc = validation_metric.get("balanced_accuracy")
    holdout_bacc = holdout_metric.get("balanced_accuracy")
    gap = (
        round(float(validation_bacc) - float(holdout_bacc), 6)
        if isinstance(validation_bacc, (int, float)) and isinstance(holdout_bacc, (int, float))
        else None
    )
    return {
        "slice_id": _slice_id(normalized[0]) if normalized else "unspecified|hunspecified|unspecified",
        "row_count": len(normalized),
        "validation_rows": len(validation_rows),
        "holdout_rows": len(holdout_rows),
        "validation_metrics": validation_metric,
        "holdout_metrics": holdout_metric,
        "validation_holdout_balanced_accuracy_gap": gap,
        "duplicate_key_severity": (audit.get("duplicate_prediction_keys") or {}).get("duplicate_key_severity"),
        "overlap_rate": (audit.get("overlapping_label_windows") or {}).get("overlap_rate"),
        "leakage_warning": audit.get("leakage_warning"),
        "previous_baseline_leakage_risk": _previous_baseline_leakage_risk(source_rows),
        "audit": {
            "duplicate_prediction_keys": audit.get("duplicate_prediction_keys"),
            "overlapping_label_windows": audit.get("overlapping_label_windows"),
            "leakage_risk_score": audit.get("leakage_risk_score"),
            "leakage_warning": audit.get("leakage_warning"),
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def build_forecast_allowed_slices(rows: list[dict], *, min_rows: int = MIN_ROWS_DEFAULT) -> dict:
    """Build allowed and abstained ticker/horizon/model slices."""

    normalized = list(normalize_forecast_actual_rows(rows))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        grouped[_slice_id(row)].append(_public_row(row))

    slice_results = {}
    allowed = []
    abstained = []
    statuses = Counter()
    for slice_id, group_rows in sorted(grouped.items()):
        stability = evaluate_slice_stability(group_rows)
        status, reasons = _status_for_slice(
            row_count=len(group_rows),
            audit={
                "duplicate_prediction_keys": stability.get("audit", {}).get("duplicate_prediction_keys"),
                "overlapping_label_windows": stability.get("audit", {}).get("overlapping_label_windows"),
                "leakage_warning": stability.get("leakage_warning"),
            },
            validation_metric=stability["validation_metrics"],
            holdout_metric=stability["holdout_metrics"],
            min_rows=min_rows,
            previous_baseline_leakage_risk=bool(stability.get("previous_baseline_leakage_risk")),
        )
        statuses[status] += 1
        item = {
            **stability,
            "status": status,
            "abstention_reason": "; ".join(reasons),
            "gate_reasons": reasons,
            "min_rows": min_rows,
        }
        slice_results[slice_id] = item
        if status == FORECAST_ALLOWED:
            allowed.append(slice_id)
        else:
            abstained.append(slice_id)

    return {
        "gate_status": "completed" if normalized else "not_ready_no_rows",
        "input_rows": len(rows),
        "normalized_rows": len(normalized),
        "min_rows": min_rows,
        "allowed_slices": allowed,
        "abstained_slices": abstained,
        "allowed_slice_count": len(allowed),
        "abstained_slice_count": len(abstained),
        "status_counts": dict(sorted(statuses.items())),
        "slice_results": slice_results,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_forecast_slice_gate_report(result: dict) -> str:
    """Render a compact robust slice gate report."""

    lines = [
        "# Robust Forecast Slice Gate",
        "",
        f"Gate status: {result.get('gate_status')}",
        f"Input rows: {result.get('input_rows')}",
        f"Allowed slices: {result.get('allowed_slice_count')}",
        f"Abstained slices: {result.get('abstained_slice_count')}",
        f"Status counts: {result.get('status_counts')}",
        "",
        "Allowed:",
    ]
    lines.extend([f"- {slice_id}" for slice_id in result.get("allowed_slices", [])] or ["- none"])
    lines.append("")
    lines.append("Abstained:")
    for slice_id in result.get("abstained_slices", [])[:20]:
        item = (result.get("slice_results") or {}).get(slice_id, {})
        lines.append(f"- {slice_id}: {item.get('status')} ({item.get('abstention_reason')})")
    if not result.get("abstained_slices"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "Slices that fail strict local validation and holdout gates abstain with an explicit reason.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build robust allowed forecast slices.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--min-rows", type=int, default=MIN_ROWS_DEFAULT)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        rows = load_forecast_accuracy_rows(args.input)
        result = build_forecast_allowed_slices(rows, min_rows=args.min_rows)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if args.format == "report":
        print(render_forecast_slice_gate_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
