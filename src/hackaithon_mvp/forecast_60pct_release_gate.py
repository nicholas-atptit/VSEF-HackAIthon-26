"""Hard 60 percent release gate for local forecast performance claims."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy, load_forecast_accuracy_rows


STATUS_GLOBAL = "forecast_release_passed_60pct_global"
STATUS_SELECTIVE = "forecast_release_passed_60pct_selective"
STATUS_SLICE_ONLY = "forecast_release_passed_60pct_slice_only"
STATUS_BLOCKED_BELOW = "forecast_release_blocked_below_60pct"
STATUS_BLOCKED_DATA = "forecast_release_blocked_data_quality"
STATUS_BLOCKED_ROWS = "forecast_release_blocked_insufficient_rows"
STATUS_BLOCKED_REUSE = "forecast_release_blocked_holdout_reuse"
MIN_SCORE = 0.60
MIN_GLOBAL_ROWS = 1000
MIN_GLOBAL_COVERAGE = 0.30
MIN_SELECTIVE_ROWS = 500
MIN_SELECTIVE_COVERAGE = 0.10
MIN_SLICE_ROWS = 300
MIN_EXPLORATORY_SLICE_ROWS = 150
CLAIM_BOUNDARY = {
    "hard_minimum_accuracy": MIN_SCORE,
    "coverage_disclosed": True,
    "final_holdout_required": True,
    "validation_only_not_final": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Forecast release is blocked unless the local final holdout clears the hard 60 percent gate."


def _num(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _int(value: Any) -> int:
    number = _num(value)
    return int(number) if number is not None else 0


def _beats(value: Any, baseline: Any) -> bool:
    left = _num(value)
    right = _num(baseline)
    return left is not None and right is not None and left > right


def _metric_at_or_above(value: Any, threshold: float = MIN_SCORE) -> bool:
    number = _num(value)
    return number is not None and number >= threshold


def _high_severity(value: Any) -> bool:
    if isinstance(value, bool):
        return bool(value)
    return str(value or "").strip().lower() in {"high", "critical", "true", "yes"}


def _has_high_data_warning(result: dict) -> tuple[bool, list[str]]:
    warnings = []
    audit = result.get("audit") if isinstance(result.get("audit"), dict) else {}
    duplicate = result.get("duplicate_key_severity") or result.get("duplicate_key_warning")
    leakage = result.get("leakage_severity") or result.get("leakage_warning")
    overlap = result.get("overlap_severity") or result.get("overlap_warning")
    if audit:
        duplicate = duplicate or audit.get("duplicate_key_severity")
        leakage = leakage or audit.get("leakage_warning") or audit.get("leakage_risk_score")
        overlap = overlap or audit.get("overlap_severity")
    if _high_severity(duplicate):
        warnings.append("duplicate_key_high_severity")
    if _high_severity(leakage):
        warnings.append("leakage_high_severity")
    if _high_severity(overlap):
        warnings.append("overlap_high_severity")
    return bool(warnings), warnings


def _hidden_holdout_reuse(result: dict) -> bool:
    return bool(
        result.get("hidden_post_hoc_tuning_on_holdout")
        or result.get("tuned_on_final_holdout")
        or result.get("holdout_selection_basis") == "post_hoc_final_holdout"
    )


def _accuracy_eval(result: dict) -> dict:
    value = result.get("accuracy_evaluation")
    return value if isinstance(value, dict) else {}


def _directional(result: dict) -> dict:
    accuracy = _accuracy_eval(result)
    directional = (accuracy.get("global") or {}).get("directional")
    return directional if isinstance(directional, dict) else {}


def _baselines(result: dict) -> dict:
    for key in ("baseline_comparison", "retained_baselines", "baselines_on_retained_rows", "holdout_baselines"):
        value = result.get(key)
        if isinstance(value, dict):
            return value
    accuracy = _accuracy_eval(result)
    value = accuracy.get("baseline_comparison")
    return value if isinstance(value, dict) else {}


def _baseline_value(baselines: dict, *keys: str) -> float | None:
    for key in keys:
        if key in baselines:
            return _num(baselines.get(key))
    return None


def _global_inputs(result: dict) -> dict[str, Any]:
    directional = _directional(result)
    baselines = _baselines(result)
    rows = (
        result.get("final_holdout_rows")
        or result.get("holdout_rows")
        or directional.get("coverage_count")
        or result.get("evaluated_row_count")
        or result.get("retained_holdout_rows")
        or 0
    )
    evaluated = result.get("evaluated_row_count") or directional.get("sample_count") or rows
    coverage = result.get("final_holdout_coverage")
    if coverage is None and evaluated:
        coverage = _int(rows) / _int(evaluated) if _int(evaluated) else None
    if coverage is None:
        coverage = 1.0 if _int(rows) else 0.0
    return {
        "accuracy": result.get("final_holdout_accuracy", result.get("global_directional_accuracy", directional.get("accuracy"))),
        "balanced_accuracy": result.get("final_holdout_balanced_accuracy", result.get("global_balanced_accuracy", directional.get("balanced_accuracy"))),
        "mcc": result.get("final_holdout_mcc", directional.get("mcc")),
        "rows": _int(rows),
        "coverage": _num(coverage) or 0.0,
        "random_baseline": _baseline_value(baselines, "random", "random_50_50", "random_50_50_baseline_accuracy"),
        "majority_baseline": _baseline_value(baselines, "majority", "majority_class", "majority_class_baseline_accuracy"),
        "previous_direction_baseline": _baseline_value(
            baselines,
            "previous_direction",
            "previous_direction_baseline_accuracy",
        ),
    }


def _selective_inputs(result: dict) -> dict[str, Any]:
    baselines = result.get("retained_baselines")
    if not isinstance(baselines, dict):
        baselines = result.get("baselines_on_retained_rows")
    if not isinstance(baselines, dict):
        baselines = {}
    rows = (
        result.get("retained_holdout_rows")
        or result.get("retained_rows")
        or result.get("retained_row_count")
        or result.get("retained_forecast_rows_count")
        or 0
    )
    coverage = result.get("retained_coverage", result.get("retained_forecast_coverage"))
    return {
        "accuracy": result.get("retained_holdout_accuracy", result.get("retained_accuracy")),
        "balanced_accuracy": result.get("retained_holdout_balanced_accuracy", result.get("retained_balanced_accuracy")),
        "mcc": result.get("retained_holdout_mcc", result.get("retained_mcc")),
        "rows": _int(rows),
        "coverage": _num(coverage) if coverage is not None else None,
        "random_baseline": _baseline_value(baselines, "random", "random_50_50", "random_50_50_baseline_accuracy"),
        "majority_baseline": _baseline_value(baselines, "majority", "majority_class", "majority_class_baseline_accuracy"),
        "previous_direction_baseline": _baseline_value(
            baselines,
            "previous_direction",
            "previous_direction_baseline_accuracy",
        ),
    }


def _gate_reasons(
    metrics: dict[str, Any],
    *,
    min_rows: int,
    min_coverage: float,
    require_majority: bool,
) -> list[str]:
    reasons = []
    accuracy = _num(metrics.get("accuracy"))
    balanced = _num(metrics.get("balanced_accuracy"))
    mcc = _num(metrics.get("mcc"))
    if not (_metric_at_or_above(accuracy) or _metric_at_or_above(balanced)):
        reasons.append("accuracy_below_60pct")
    if int(metrics.get("rows") or 0) < min_rows:
        reasons.append("insufficient_holdout_rows")
    coverage = _num(metrics.get("coverage"))
    if coverage is None:
        reasons.append("coverage_not_reported")
    elif coverage < min_coverage:
        reasons.append("coverage_below_minimum")
    if mcc is None or mcc <= 0:
        reasons.append("mcc_not_positive")
    if not _beats(balanced if balanced is not None else accuracy, metrics.get("random_baseline")):
        reasons.append("does_not_beat_random")
    if require_majority and not _beats(balanced if balanced is not None else accuracy, metrics.get("majority_baseline")):
        reasons.append("does_not_beat_majority")
    return reasons


def _group_slice_rows(rows: list[dict]) -> dict[tuple[str, str, str], list[dict]]:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        ticker = str(row.get("ticker") or "unspecified").upper()
        horizon = str(row.get("horizon") or "unspecified")
        model_id = str(row.get("model_id") or row.get("model_key") or "unspecified")
        groups[(ticker, horizon, model_id)].append(row)
    return dict(groups)


def evaluate_60pct_slice_gate(rows: list[dict]) -> dict:
    """Evaluate 60 percent release gates for ticker/horizon/model slices."""

    slice_results = []
    for (ticker, horizon, model_id), group_rows in sorted(_group_slice_rows(rows).items()):
        evaluation = evaluate_forecast_accuracy(group_rows)
        directional = evaluation["global"]["directional"]
        baselines = evaluation["baseline_comparison"]
        data_issue = any(
            _high_severity(row.get("leakage_warning"))
            or _high_severity(row.get("duplicate_key_severity"))
            or _high_severity(row.get("overlap_severity"))
            for row in group_rows
        )
        rows_count = int(directional.get("coverage_count") or 0)
        balanced = directional.get("balanced_accuracy")
        accuracy = directional.get("accuracy")
        mcc = directional.get("mcc")
        reasons = []
        if not _metric_at_or_above(balanced):
            reasons.append("slice_balanced_accuracy_below_60pct")
        if rows_count < MIN_EXPLORATORY_SLICE_ROWS:
            reasons.append("slice_rows_below_exploratory_minimum")
        if mcc is None or mcc <= 0:
            reasons.append("slice_mcc_not_positive")
        if data_issue:
            reasons.append("slice_data_quality_warning")
        if not _beats(balanced, baselines.get("random_50_50_baseline_accuracy")):
            reasons.append("slice_does_not_beat_random")
        preferred = (
            not reasons
            and rows_count >= MIN_SLICE_ROWS
            and _beats(balanced, baselines.get("majority_class_baseline_accuracy"))
        )
        exploratory = not reasons and rows_count >= MIN_EXPLORATORY_SLICE_ROWS
        if preferred:
            status = STATUS_SLICE_ONLY
        elif exploratory:
            status = "slice_only_exploratory"
        elif data_issue:
            status = STATUS_BLOCKED_DATA
        elif rows_count < MIN_EXPLORATORY_SLICE_ROWS:
            status = STATUS_BLOCKED_ROWS
        else:
            status = STATUS_BLOCKED_BELOW
        slice_results.append(
            {
                "slice_id": f"{ticker}|h{horizon}|{model_id}",
                "ticker": ticker,
                "horizon": horizon,
                "model_id": model_id,
                "status": status,
                "rows": rows_count,
                "accuracy": accuracy,
                "balanced_accuracy": balanced,
                "mcc": mcc,
                "wilson_accuracy_interval": directional.get("wilson_accuracy_interval"),
                "random_baseline": baselines.get("random_50_50_baseline_accuracy"),
                "majority_baseline": baselines.get("majority_class_baseline_accuracy"),
                "previous_direction_baseline": baselines.get("previous_direction_baseline_accuracy"),
                "beats_random": _beats(balanced, baselines.get("random_50_50_baseline_accuracy")),
                "beats_majority": _beats(balanced, baselines.get("majority_class_baseline_accuracy")),
                "exploratory_only": exploratory and not preferred,
                "reasons": reasons,
            }
        )
    preferred_slices = [item for item in slice_results if item["status"] == STATUS_SLICE_ONLY]
    exploratory_slices = [item for item in slice_results if item["status"] == "slice_only_exploratory"]
    best = None
    candidates = [item for item in slice_results if isinstance(item.get("balanced_accuracy"), (int, float))]
    if candidates:
        best = sorted(candidates, key=lambda item: (item["balanced_accuracy"], item["rows"]), reverse=True)[0]
    return {
        "slice_gate_status": STATUS_SLICE_ONLY if preferred_slices else STATUS_BLOCKED_BELOW,
        "slice_count": len(slice_results),
        "passed_slice_count": len(preferred_slices),
        "exploratory_slice_count": len(exploratory_slices),
        "passed_slices": preferred_slices,
        "exploratory_slices": exploratory_slices,
        "best_slice": best,
        "slice_results": slice_results,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def evaluate_60pct_release_gate(result: dict) -> dict:
    """Evaluate global, selective, and slice-only hard 60 percent release gates."""

    data_blocked, data_reasons = _has_high_data_warning(result)
    holdout_reuse = _hidden_holdout_reuse(result)
    global_metrics = _global_inputs(result)
    selective_metrics = _selective_inputs(result)
    global_reasons = _gate_reasons(
        global_metrics,
        min_rows=MIN_GLOBAL_ROWS,
        min_coverage=MIN_GLOBAL_COVERAGE,
        require_majority=True,
    )
    selective_reasons = _gate_reasons(
        selective_metrics,
        min_rows=MIN_SELECTIVE_ROWS,
        min_coverage=MIN_SELECTIVE_COVERAGE,
        require_majority=False,
    )
    if selective_metrics.get("coverage") is None:
        selective_reasons.append("retained_coverage_not_reported")
    rows = result.get("retained_forecast_rows")
    if not isinstance(rows, list):
        rows = result.get("holdout_forecast_rows") if isinstance(result.get("holdout_forecast_rows"), list) else []
    slice_gate = result.get("slice_gate") if isinstance(result.get("slice_gate"), dict) else evaluate_60pct_slice_gate(rows)

    if holdout_reuse:
        status = STATUS_BLOCKED_REUSE
    elif data_blocked:
        status = STATUS_BLOCKED_DATA
    elif not global_reasons:
        status = STATUS_GLOBAL
    elif not selective_reasons:
        status = STATUS_SELECTIVE
    elif slice_gate.get("passed_slice_count"):
        status = STATUS_SLICE_ONLY
    elif "insufficient_holdout_rows" in global_reasons and "insufficient_holdout_rows" in selective_reasons:
        status = STATUS_BLOCKED_ROWS
    else:
        status = STATUS_BLOCKED_BELOW

    previous_dominates = False
    for metrics in (global_metrics, selective_metrics):
        score = _num(metrics.get("balanced_accuracy")) or _num(metrics.get("accuracy"))
        previous = _num(metrics.get("previous_direction_baseline"))
        if score is not None and previous is not None and previous >= score:
            previous_dominates = True
    global_passed = status == STATUS_GLOBAL
    selective_passed = status == STATUS_SELECTIVE
    slice_passed = status == STATUS_SLICE_ONLY
    broad_allowed = bool(global_passed and not previous_dominates)
    return {
        "forecast_release_status": status,
        "global_release_passed": global_passed,
        "selective_release_passed": selective_passed,
        "slice_only_passed": slice_passed,
        "forecast_release_allowed": global_passed or selective_passed,
        "broad_performance_claim_allowed": broad_allowed,
        "previous_direction_dominates": previous_dominates,
        "global_gate": {
            "passed": not global_reasons and not data_blocked and not holdout_reuse,
            "metrics": global_metrics,
            "reasons": global_reasons,
            "minimum_rows": MIN_GLOBAL_ROWS,
            "minimum_coverage": MIN_GLOBAL_COVERAGE,
        },
        "selective_gate": {
            "passed": not selective_reasons and not data_blocked and not holdout_reuse,
            "metrics": selective_metrics,
            "reasons": sorted(set(selective_reasons)),
            "minimum_rows": MIN_SELECTIVE_ROWS,
            "minimum_coverage": MIN_SELECTIVE_COVERAGE,
        },
        "slice_gate": slice_gate,
        "data_quality_reasons": data_reasons,
        "holdout_reuse_blocked": holdout_reuse,
        "threshold": MIN_SCORE,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def _fmt(value: Any) -> str:
    return "unavailable" if value is None else str(value)


def render_60pct_gate_report(result: dict) -> str:
    """Render a compact hard-gate report."""

    global_gate = result.get("global_gate") or {}
    selective_gate = result.get("selective_gate") or {}
    global_metrics = global_gate.get("metrics") or {}
    selective_metrics = selective_gate.get("metrics") or {}
    slice_gate = result.get("slice_gate") or {}
    lines = [
        "# 60% Forecast Release Gate",
        "",
        f"Forecast release status: {result.get('forecast_release_status')}",
        f"Global gate passed: {result.get('global_release_passed')}",
        f"Selective gate passed: {result.get('selective_release_passed')}",
        f"Slice-only gate passed: {result.get('slice_only_passed')}",
        f"Broad claim allowed: {result.get('broad_performance_claim_allowed')}",
        "",
        "Global final holdout:",
        f"- rows: {_fmt(global_metrics.get('rows'))}",
        f"- coverage: {_fmt(global_metrics.get('coverage'))}",
        f"- accuracy: {_fmt(global_metrics.get('accuracy'))}",
        f"- balanced accuracy: {_fmt(global_metrics.get('balanced_accuracy'))}",
        f"- MCC: {_fmt(global_metrics.get('mcc'))}",
        f"- block reasons: {global_gate.get('reasons') or []}",
        "",
        "Selective retained final holdout:",
        f"- rows: {_fmt(selective_metrics.get('rows'))}",
        f"- coverage: {_fmt(selective_metrics.get('coverage'))}",
        f"- accuracy: {_fmt(selective_metrics.get('accuracy'))}",
        f"- balanced accuracy: {_fmt(selective_metrics.get('balanced_accuracy'))}",
        f"- MCC: {_fmt(selective_metrics.get('mcc'))}",
        f"- block reasons: {selective_gate.get('reasons') or []}",
        "",
        "Slice-level gate:",
        f"- preferred passed slices: {slice_gate.get('passed_slice_count')}",
        f"- exploratory slices: {slice_gate.get('exploratory_slice_count')}",
        f"- best slice: {slice_gate.get('best_slice')}",
        "",
        "Boundary:",
        "Validation-only results do not satisfy this gate.",
        "Coverage and row counts must be disclosed with any retained metric.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a hard 60 percent forecast release gate.")
    parser.add_argument("--input", default=None, help="Optional forecast-vs-actual JSONL input for slice-level gating.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = load_forecast_accuracy_rows(args.input) if args.input else []
    accuracy = evaluate_forecast_accuracy(rows)
    directional = accuracy["global"]["directional"]
    result = evaluate_60pct_release_gate(
        {
            "accuracy_evaluation": accuracy,
            "evaluated_row_count": accuracy.get("evaluated_row_count"),
            "final_holdout_accuracy": directional.get("accuracy"),
            "final_holdout_balanced_accuracy": directional.get("balanced_accuracy"),
            "final_holdout_mcc": directional.get("mcc"),
            "final_holdout_rows": directional.get("coverage_count"),
            "final_holdout_coverage": 1.0 if directional.get("coverage_count") else 0.0,
            "baseline_comparison": accuracy.get("baseline_comparison"),
            "retained_forecast_rows": rows,
        }
    )
    if args.format == "report":
        print(render_60pct_gate_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
