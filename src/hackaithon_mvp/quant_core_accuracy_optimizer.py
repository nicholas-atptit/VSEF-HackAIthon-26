"""Validation-split policy optimizer for Quant Core diagnostic accuracy."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from typing import Any

from src.hackaithon_mvp.forecast_actual_evaluation import (
    DIRECTIONAL_DIAGNOSTICS,
    evaluate_forecast_vs_actual,
    load_forecast_actual_rows,
    validate_forecast_actual_row,
)
from src.hackaithon_mvp.legacy_forecast_actual_adapter import (
    convert_legacy_rows_to_forecast_actual,
    load_legacy_rows,
)
from src.hackaithon_mvp.quant_core_calibration import (
    build_confidence_calibration_report,
    build_score_calibration_report,
)
from src.hackaithon_mvp.quant_core_performance_attribution import build_performance_attribution


BALANCED_ACCURACY_THRESHOLDS = (0.50, 0.515, 0.525, 0.535, 0.55, 0.575, 0.60)
TOP_PERCENTILE_THRESHOLDS = (50, 60, 70, 80, 90, 95)
DEFAULT_MIN_SAMPLE_COUNT = 30
INVERSION_MIN_SAMPLE_COUNT = 100
INVERSION_MAX_BALANCED_ACCURACY = 0.475
INVERSION_MIN_IMPROVEMENT = 0.03
NON_CLAIM_TEXT = "Diagnostic research output only; validation split metrics are not production performance claims."
CLAIM_BOUNDARY = {
    "baseline_ml_only": True,
    "diagnostic_research_only": True,
    "validation_split_required": True,
    "no_live_data": True,
    "no_provider_api_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "no_generated_actual_labels": True,
}


_ROW_INDEX_PATTERN = re.compile(r"^row_index_(\d+)$")


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_forecast_actual_row(row)
    merged = dict(row)
    merged.update(normalized)
    return merged


def _ratio_split_index(row_count: int, calibration_ratio: float) -> int:
    if not 0 < calibration_ratio < 1:
        raise ValueError("calibration_ratio must be between 0 and 1")
    if row_count <= 1:
        return row_count
    split_index = int(row_count * calibration_ratio)
    return min(max(split_index, 1), row_count - 1)


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text or _ROW_INDEX_PATTERN.match(text):
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def split_rows_for_policy_validation(
    rows: tuple[dict, ...],
    *,
    split_field: str | None = "prediction_timestamp",
    calibration_ratio: float = 0.6,
) -> dict:
    """Split rows into calibration and validation partitions without shuffling."""

    normalized_rows = tuple(_normalize_row(row) for row in rows)
    split_index = _ratio_split_index(len(normalized_rows), calibration_ratio)
    warnings: list[str] = []
    ordered_rows = normalized_rows
    split_method = "deterministic_input_order"

    if split_field and normalized_rows and all(row.get(split_field) not in (None, "") for row in normalized_rows):
        values = [str(row[split_field]).strip() for row in normalized_rows]
        if all(_ROW_INDEX_PATTERN.match(value) for value in values):
            split_method = "synthetic_row_index_order"
        else:
            parsed = [_parse_timestamp(value) for value in values]
            if all(value is not None for value in parsed):
                ordered_rows = tuple(
                    row
                    for _, _, row in sorted(
                        zip(parsed, range(len(normalized_rows)), normalized_rows),
                        key=lambda item: (item[0], item[1]),
                    )
                )
                split_method = f"chronological_{split_field}"
            else:
                warnings.append("split_field_not_timestamp_like_using_input_order")
    else:
        if split_field:
            warnings.append("split_field_missing_using_input_order")
        else:
            warnings.append("split_field_disabled_using_input_order")

    if len(normalized_rows) <= 1:
        warnings.append("validation_split_unavailable_for_single_row")
    return {
        "calibration_rows": ordered_rows[:split_index],
        "validation_rows": ordered_rows[split_index:],
        "split_method": split_method,
        "warnings": warnings,
    }


def _group_key(row: dict[str, Any], group_fields: tuple[str, ...]) -> dict[str, str]:
    return {field: "unspecified" if row.get(field) in (None, "") else str(row.get(field)) for field in group_fields}


def _group_key_id(group_key: dict[str, str], group_fields: tuple[str, ...]) -> str:
    return "|".join(f"{field}={group_key[field]}" for field in group_fields)


def _row_group_id(row: dict[str, Any], group_fields: tuple[str, ...]) -> str:
    return _group_key_id(_group_key(row, group_fields), group_fields)


def _numeric_value(row: dict[str, Any], field: str) -> float | None:
    value = row.get(field)
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _percentile_threshold(values: list[float], percentile: int) -> float:
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * percentile / 100)
    return sorted_values[index]


def _policy_summary(policy: dict) -> dict:
    return {
        "policy_name": policy["policy_name"],
        "policy_family": policy["policy_family"],
        "threshold": policy.get("threshold"),
        "percentile": policy.get("percentile"),
        "field": policy.get("field"),
        "allowed_group_count": len(policy.get("allowed_group_ids", ())),
        "suppressed_group_count": len(policy.get("suppressed_group_ids", ())),
        "inversion_group_count": len(policy.get("inversion_group_ids", ())),
        "selectable": policy.get("selectable", True),
        "warnings": list(policy.get("warnings", ())),
    }


def _build_group_policy(
    *,
    policy_name: str,
    policy_family: str,
    group_fields: tuple[str, ...],
    groups: list[dict],
    threshold: float | None = None,
    allowed_group_ids: set[str] | None = None,
    suppressed_group_ids: set[str] | None = None,
    selectable: bool = True,
    warnings: list[str] | None = None,
) -> dict:
    allowed = allowed_group_ids or set()
    suppressed = suppressed_group_ids or set()
    group_rules = []
    for group in groups:
        group_rules.append(
            {
                "group_key": dict(group["group_key"]),
                "group_key_id": group["group_key_id"],
                "sample_count": group["sample_count"],
                "balanced_directional_accuracy": group["balanced_directional_accuracy"],
                "directional_accuracy": group["directional_accuracy"],
                "is_allowed": group["group_key_id"] in allowed,
                "is_suppressed": group["group_key_id"] in suppressed,
                "is_sample_sufficient": group["is_sample_sufficient"],
            }
        )
    return {
        "policy_name": policy_name,
        "policy_family": policy_family,
        "group_fields": tuple(group_fields),
        "threshold": threshold,
        "allowed_group_ids": sorted(allowed),
        "suppressed_group_ids": sorted(suppressed),
        "group_rules": group_rules,
        "selectable": selectable,
        "warnings": list(warnings or ()),
    }


def _build_score_threshold_policies(
    calibration_rows: tuple[dict[str, Any], ...],
    *,
    field: str,
    policy_family: str,
) -> list[dict]:
    scored_values = [
        value
        for row in calibration_rows
        if row["forecast_diagnostic"] in DIRECTIONAL_DIAGNOSTICS
        for value in [_numeric_value(row, field)]
        if value is not None
    ]
    if not scored_values:
        return []
    report = (
        build_score_calibration_report(calibration_rows)
        if field == "diagnostic_score"
        else build_confidence_calibration_report(calibration_rows)
    )
    warnings: list[str] = []
    selectable = True
    if report.get("monotonicity_check") != "non_decreasing_by_score":
        warnings.append("ranking_not_monotonic_on_calibration")
        selectable = False
    if report.get("top_bin_accuracy") is not None and report.get("bottom_bin_accuracy") is not None:
        if report["top_bin_accuracy"] < report["bottom_bin_accuracy"]:
            warnings.append("top_bin_below_bottom_bin_on_calibration")
            selectable = False
    if report.get("ranking_warning"):
        warnings.append(str(report["ranking_warning"]))
        selectable = False

    policies = []
    for percentile in TOP_PERCENTILE_THRESHOLDS:
        threshold = _percentile_threshold(scored_values, percentile)
        policies.append(
            {
                "policy_name": f"{policy_family}_p{percentile}",
                "policy_family": policy_family,
                "field": field,
                "percentile": percentile,
                "threshold_value": threshold,
                "selectable": selectable,
                "warnings": list(warnings),
                "calibration_report": {
                    "eligible_rows": report["eligible_rows"],
                    "monotonicity_check": report["monotonicity_check"],
                    "ranking_warning": report["ranking_warning"],
                    "top_bin_accuracy": report["top_bin_accuracy"],
                    "bottom_bin_accuracy": report["bottom_bin_accuracy"],
                    "top_slice_accuracy": report.get("top_slice_accuracy"),
                },
            }
        )
    return policies


def _build_validated_inversion_policy(
    groups: list[dict],
    group_fields: tuple[str, ...],
) -> dict | None:
    inversion_ids: set[str] = set()
    group_rules = []
    for group in groups:
        balanced_accuracy = group["balanced_directional_accuracy"]
        inverted_balanced_accuracy = None if balanced_accuracy is None else round(1 - balanced_accuracy, 6)
        improvement = None if inverted_balanced_accuracy is None else round(inverted_balanced_accuracy - balanced_accuracy, 6)
        eligible = (
            group["sample_count"] >= INVERSION_MIN_SAMPLE_COUNT
            and balanced_accuracy is not None
            and balanced_accuracy <= INVERSION_MAX_BALANCED_ACCURACY
            and group["actual_positive_count"] > 0
            and group["actual_negative_count"] > 0
            and improvement is not None
            and improvement >= INVERSION_MIN_IMPROVEMENT
        )
        if eligible:
            inversion_ids.add(group["group_key_id"])
        group_rules.append(
            {
                "group_key": dict(group["group_key"]),
                "group_key_id": group["group_key_id"],
                "sample_count": group["sample_count"],
                "balanced_directional_accuracy": balanced_accuracy,
                "inverted_balanced_directional_accuracy": inverted_balanced_accuracy,
                "inversion_improvement": improvement,
                "is_inversion_group": eligible,
            }
        )
    if not inversion_ids:
        return None
    return {
        "policy_name": "validated_inversion",
        "policy_family": "validated_inversion",
        "group_fields": tuple(group_fields),
        "inversion_group_ids": sorted(inversion_ids),
        "group_rules": group_rules,
        "selectable": True,
        "warnings": ["inversion_is_validation_scored_before_use"],
    }


def build_candidate_policies(
    calibration_rows: tuple[dict, ...],
    *,
    group_fields: tuple[str, ...] = ("ticker", "timeframe", "horizon_steps", "model_family"),
) -> tuple[dict, ...]:
    """Build deterministic policy candidates from calibration rows only."""

    normalized_rows = tuple(_normalize_row(row) for row in calibration_rows)
    attribution = build_performance_attribution(normalized_rows, group_fields=group_fields)
    groups = list(attribution["groups"])
    candidates: list[dict] = [
        {
            "policy_name": "baseline_pass_through",
            "policy_family": "baseline_pass_through",
            "selectable": True,
            "warnings": [],
        }
    ]

    for threshold in BALANCED_ACCURACY_THRESHOLDS:
        allowed = {
            group["group_key_id"]
            for group in groups
            if group["is_sample_sufficient"]
            and group["balanced_directional_accuracy"] is not None
            and group["balanced_directional_accuracy"] >= threshold
        }
        candidates.append(
            _build_group_policy(
                policy_name=f"eligible_slice_gate_bacc_{threshold:.3f}",
                policy_family="eligible_slice_gate",
                group_fields=group_fields,
                groups=groups,
                threshold=threshold,
                allowed_group_ids=allowed,
            )
        )

    strong_allowed = {
        group["group_key_id"]
        for group in groups
        if group["is_sample_sufficient"]
        and group["balanced_directional_accuracy"] is not None
        and group["balanced_directional_accuracy"] >= 0.55
    }
    candidates.append(
        _build_group_policy(
            policy_name="strong_slice_only",
            policy_family="strong_slice_only",
            group_fields=group_fields,
            groups=groups,
            threshold=0.55,
            allowed_group_ids=strong_allowed,
        )
    )

    weak_suppressed = {
        group["group_key_id"]
        for group in groups
        if group["is_sample_sufficient"]
        and group["balanced_directional_accuracy"] is not None
        and group["balanced_directional_accuracy"] < 0.50
    }
    candidates.append(
        _build_group_policy(
            policy_name="weak_slice_abstention",
            policy_family="weak_slice_abstention",
            group_fields=group_fields,
            groups=groups,
            suppressed_group_ids=weak_suppressed,
        )
    )

    inversion_policy = _build_validated_inversion_policy(groups, group_fields)
    if inversion_policy is not None:
        candidates.append(inversion_policy)

    candidates.extend(
        _build_score_threshold_policies(
            normalized_rows,
            field="diagnostic_score",
            policy_family="score_threshold_gate",
        )
    )
    candidates.extend(
        _build_score_threshold_policies(
            normalized_rows,
            field="confidence",
            policy_family="confidence_threshold_gate",
        )
    )

    for field, policy_family in (("ticker", "ticker_whitelist_gate"), ("model_family", "model_family_router")):
        field_attribution = build_performance_attribution(normalized_rows, group_fields=(field,))
        field_groups = list(field_attribution["groups"])
        for threshold in BALANCED_ACCURACY_THRESHOLDS:
            allowed = {
                group["group_key_id"]
                for group in field_groups
                if group["is_sample_sufficient"]
                and group["balanced_directional_accuracy"] is not None
                and group["balanced_directional_accuracy"] >= threshold
            }
            candidates.append(
                _build_group_policy(
                    policy_name=f"{policy_family}_bacc_{threshold:.3f}",
                    policy_family=policy_family,
                    group_fields=(field,),
                    groups=field_groups,
                    threshold=threshold,
                    allowed_group_ids=allowed,
                )
            )

    return tuple(candidates)


def _invert_diagnostic_label(label: str) -> str:
    if label == "positive_bias":
        return "negative_bias"
    if label == "negative_bias":
        return "positive_bias"
    return label


def apply_accuracy_policy(
    rows: tuple[dict, ...],
    policy: dict,
) -> tuple[dict, ...]:
    """Apply a candidate policy without upgrading non-directional rows."""

    policy_family = str(policy.get("policy_family") or policy.get("policy_name") or "")
    policy_name = str(policy.get("policy_name") or policy_family)
    group_fields = tuple(policy.get("group_fields", ()))
    allowed_group_ids = set(policy.get("allowed_group_ids", ()))
    suppressed_group_ids = set(policy.get("suppressed_group_ids", ()))
    inversion_group_ids = set(policy.get("inversion_group_ids", ()))
    output_rows: list[dict[str, Any]] = []

    for row in rows:
        output = _normalize_row(row)
        original_label = output["forecast_diagnostic"]
        output["pre_policy_forecast_diagnostic"] = original_label
        output["accuracy_policy_applied"] = True
        output["accuracy_policy_name"] = policy_name
        output["accuracy_policy_reason"] = "preserved"
        if original_label not in DIRECTIONAL_DIAGNOSTICS:
            output["accuracy_policy_reason"] = "non_directional_preserved"
            output_rows.append(output)
            continue

        group_id = _row_group_id(output, group_fields) if group_fields else None
        if policy_family == "baseline_pass_through":
            output["accuracy_policy_reason"] = "baseline_pass_through"
        elif policy_family in {"eligible_slice_gate", "strong_slice_only", "ticker_whitelist_gate", "model_family_router"}:
            if group_id not in allowed_group_ids:
                output["forecast_diagnostic"] = "neutral_or_uncertain"
                output["accuracy_policy_reason"] = "group_not_allowed"
            else:
                output["accuracy_policy_reason"] = "group_allowed"
        elif policy_family == "weak_slice_abstention":
            if group_id in suppressed_group_ids:
                output["forecast_diagnostic"] = "neutral_or_uncertain"
                output["accuracy_policy_reason"] = "weak_group_suppressed"
        elif policy_family == "validated_inversion":
            if group_id in inversion_group_ids:
                output["forecast_diagnostic"] = _invert_diagnostic_label(original_label)
                output["accuracy_policy_reason"] = "validated_inversion_applied"
        elif policy_family in {"score_threshold_gate", "confidence_threshold_gate"}:
            field = str(policy.get("field"))
            threshold_value = policy.get("threshold_value")
            score_value = _numeric_value(output, field)
            if score_value is None or threshold_value is None or score_value < float(threshold_value):
                output["forecast_diagnostic"] = "neutral_or_uncertain"
                output["accuracy_policy_reason"] = "score_below_policy_threshold"
            else:
                output["accuracy_policy_reason"] = "score_met_policy_threshold"
        else:
            output["forecast_diagnostic"] = "neutral_or_uncertain"
            output["accuracy_policy_reason"] = "unsupported_policy_family"
        output_rows.append(output)
    return tuple(output_rows)


def evaluate_accuracy_policy(
    rows: tuple[dict, ...],
    policy: dict,
) -> dict:
    """Evaluate a policy through the existing forecast-actual evaluator."""

    evaluated = evaluate_forecast_vs_actual(apply_accuracy_policy(rows, policy))
    return {
        "policy_name": str(policy.get("policy_name")),
        "policy_family": str(policy.get("policy_family")),
        "rows_total": evaluated["rows_total"],
        "eligible_directional_rows": evaluated["eligible_directional_rows"],
        "abstained_rows": evaluated["abstained_rows"],
        "directional_accuracy": evaluated["directional_accuracy"],
        "balanced_directional_accuracy": evaluated["balanced_directional_accuracy"],
        "coverage_ratio": evaluated["coverage_ratio"],
        "abstention_ratio": evaluated["abstention_ratio"],
        "correct_directional_rows": evaluated["correct_directional_rows"],
        "incorrect_directional_rows": evaluated["incorrect_directional_rows"],
        "non_claim": NON_CLAIM_TEXT,
    }


def _metric_value(result: dict, objective: str) -> float | None:
    value = result.get(objective)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _candidate_result(
    policy: dict,
    calibration_result: dict,
    validation_result: dict,
    *,
    baseline_validation: dict,
    min_validation_coverage: float,
    objective: str,
) -> dict:
    validation_metric = _metric_value(validation_result, objective)
    baseline_metric = _metric_value(baseline_validation, objective)
    validation_coverage = validation_result.get("coverage_ratio")
    coverage_ok = isinstance(validation_coverage, (int, float)) and validation_coverage >= min_validation_coverage
    selectable = bool(policy.get("selectable", True)) and coverage_ok and validation_metric is not None
    return {
        "policy": _policy_summary(policy),
        "calibration_result": calibration_result,
        "validation_result": validation_result,
        "validation_objective": objective,
        "validation_objective_value": validation_metric,
        "validation_improvement_vs_baseline": None
        if validation_metric is None or baseline_metric is None
        else round(validation_metric - baseline_metric, 6),
        "validation_coverage_ok": coverage_ok,
        "selectable": selectable,
    }


def _frontier(candidate_results: list[dict], objective: str) -> list[dict]:
    points = []
    for result in candidate_results:
        validation = result["validation_result"]
        metric = _metric_value(validation, objective)
        coverage = validation.get("coverage_ratio")
        if metric is None or not isinstance(coverage, (int, float)):
            continue
        dominated = False
        for other in candidate_results:
            other_validation = other["validation_result"]
            other_metric = _metric_value(other_validation, objective)
            other_coverage = other_validation.get("coverage_ratio")
            if other_metric is None or not isinstance(other_coverage, (int, float)):
                continue
            if other_metric >= metric and other_coverage >= coverage and (
                other_metric > metric or other_coverage > coverage
            ):
                dominated = True
                break
        if not dominated:
            points.append(
                {
                    "policy_name": result["policy"]["policy_name"],
                    "policy_family": result["policy"]["policy_family"],
                    "coverage_ratio": coverage,
                    "directional_accuracy": validation["directional_accuracy"],
                    "balanced_directional_accuracy": validation["balanced_directional_accuracy"],
                    "abstention_ratio": validation["abstention_ratio"],
                    "selectable": result["selectable"],
                }
            )
    return sorted(points, key=lambda item: (item["coverage_ratio"], item[objective] or -1), reverse=True)


def _select_best_policy(
    candidates: tuple[dict, ...],
    candidate_results: list[dict],
    baseline_validation: dict,
    objective: str,
) -> tuple[dict, dict, list[str]]:
    warnings: list[str] = []
    baseline_metric = _metric_value(baseline_validation, objective)
    selectable_results = [result for result in candidate_results if result["selectable"]]
    if not selectable_results:
        warnings.append("no_selectable_policy")
        return candidates[0], baseline_validation, warnings
    selectable_results.sort(
        key=lambda result: (
            _metric_value(result["validation_result"], objective) or -1,
            result["validation_result"].get("coverage_ratio") or 0,
            -len(result["policy"]["warnings"]),
        ),
        reverse=True,
    )
    best_result = selectable_results[0]
    best_metric = _metric_value(best_result["validation_result"], objective)
    if baseline_metric is not None and best_metric is not None and best_metric <= baseline_metric:
        warnings.append(f"no_policy_improved_validation_{objective}")
        baseline_candidate = next(
            result for result in candidate_results if result["policy"]["policy_name"] == "baseline_pass_through"
        )
        best_result = baseline_candidate
    policy_by_name = {policy["policy_name"]: policy for policy in candidates}
    return policy_by_name[best_result["policy"]["policy_name"]], best_result["validation_result"], warnings


def run_accuracy_optimization(
    rows: tuple[dict, ...],
    *,
    calibration_ratio: float = 0.6,
    min_validation_coverage: float = 0.05,
    objective: str = "balanced_directional_accuracy",
) -> dict:
    """Run calibration-only policy search and validation-only policy selection."""

    if not 0 <= min_validation_coverage <= 1:
        raise ValueError("min_validation_coverage must be between 0 and 1")
    split = split_rows_for_policy_validation(rows, calibration_ratio=calibration_ratio)
    calibration_rows = split["calibration_rows"]
    validation_rows = split["validation_rows"]
    candidates = build_candidate_policies(calibration_rows)
    baseline_policy = candidates[0]
    baseline_calibration = evaluate_accuracy_policy(calibration_rows, baseline_policy)
    baseline_validation = evaluate_accuracy_policy(validation_rows, baseline_policy)

    candidate_results = []
    for policy in candidates:
        calibration_result = evaluate_accuracy_policy(calibration_rows, policy)
        validation_result = evaluate_accuracy_policy(validation_rows, policy)
        candidate_results.append(
            _candidate_result(
                policy,
                calibration_result,
                validation_result,
                baseline_validation=baseline_validation,
                min_validation_coverage=min_validation_coverage,
                objective=objective,
            )
        )

    best_policy, best_validation_result, selection_warnings = _select_best_policy(
        candidates,
        candidate_results,
        baseline_validation,
        objective,
    )
    warnings = list(split["warnings"]) + selection_warnings
    baseline_coverage = baseline_validation.get("coverage_ratio")
    best_coverage = best_validation_result.get("coverage_ratio")
    baseline_metric = _metric_value(baseline_validation, objective)
    best_metric = _metric_value(best_validation_result, objective)
    if (
        baseline_metric is not None
        and best_metric is not None
        and best_metric > baseline_metric
        and isinstance(baseline_coverage, (int, float))
        and isinstance(best_coverage, (int, float))
        and best_coverage < baseline_coverage * 0.5
    ):
        warnings.append("best_policy_improves_validation_metric_with_large_coverage_reduction")

    return {
        "split_method": split["split_method"],
        "calibration_row_count": len(calibration_rows),
        "validation_row_count": len(validation_rows),
        "baseline_calibration": baseline_calibration,
        "baseline_validation": baseline_validation,
        "candidate_count": len(candidates),
        "candidate_results": candidate_results,
        "best_policy": best_policy,
        "best_policy_summary": _policy_summary(best_policy),
        "best_validation_result": best_validation_result,
        "coverage_accuracy_frontier": _frontier(candidate_results, objective),
        "warnings": sorted(set(warnings)),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_gate_policy_from_accuracy_optimizer(best_policy: dict) -> dict:
    """Convert compatible optimizer policies into Quant Core calibration gate rules."""

    policy_family = best_policy.get("policy_family")
    if policy_family not in {
        "eligible_slice_gate",
        "strong_slice_only",
        "weak_slice_abstention",
        "ticker_whitelist_gate",
        "model_family_router",
    }:
        return {
            "conversion_status": "not_convertible",
            "warnings": [f"policy_family_not_supported_by_calibration_gate: {policy_family}"],
            "non_claim": NON_CLAIM_TEXT,
        }

    rules = []
    for rule in best_policy.get("group_rules", ()):
        if policy_family == "weak_slice_abstention":
            eligible = not bool(rule.get("is_suppressed"))
        else:
            eligible = bool(rule.get("is_allowed"))
        balanced_accuracy = rule.get("balanced_directional_accuracy")
        rules.append(
            {
                "match": dict(rule["group_key"]),
                "group_key_id": rule["group_key_id"],
                "sample_count": rule["sample_count"],
                "balanced_directional_accuracy": balanced_accuracy,
                "directional_accuracy": rule.get("directional_accuracy"),
                "is_sample_sufficient": bool(rule.get("is_sample_sufficient")),
                "is_directionally_eligible": eligible,
                "is_strong_group": balanced_accuracy is not None and balanced_accuracy >= 0.55,
                "is_weak_group": balanced_accuracy is not None and balanced_accuracy < 0.50,
            }
        )
    return {
        "conversion_status": "converted",
        "policy": {
            "min_balanced_accuracy": best_policy.get("threshold"),
            "strong_balanced_accuracy": 0.55,
            "min_sample_count": DEFAULT_MIN_SAMPLE_COUNT,
            "group_fields": tuple(best_policy.get("group_fields", ())),
            "rules": rules,
            "eligible_group_count": len([rule for rule in rules if rule["is_directionally_eligible"]]),
            "weak_group_count": len([rule for rule in rules if rule["is_weak_group"]]),
            "strong_group_count": len([rule for rule in rules if rule["is_strong_group"]]),
            "non_claim": NON_CLAIM_TEXT,
        },
        "warnings": [],
        "non_claim": NON_CLAIM_TEXT,
    }


def _load_rows_from_args(args: argparse.Namespace) -> tuple[dict, ...]:
    if args.legacy:
        legacy_rows = load_legacy_rows(args.input)
        return convert_legacy_rows_to_forecast_actual(
            legacy_rows,
            default_ticker=args.ticker,
            default_timeframe=args.timeframe,
            default_horizon_steps=args.horizon_steps,
            allow_row_index_timestamp=args.allow_row_index_timestamp,
            source_name=args.input,
        )
    return load_forecast_actual_rows(args.input)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulate validation-split Quant Core diagnostic policies.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--horizon-steps", type=int, default=None)
    parser.add_argument("--allow-row-index-timestamp", action="store_true")
    parser.add_argument("--calibration-ratio", type=float, default=0.6)
    parser.add_argument("--min-validation-coverage", type=float, default=0.05)
    parser.add_argument("--format", choices=("json",), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        rows = _load_rows_from_args(args)
        result = run_accuracy_optimization(
            rows,
            calibration_ratio=args.calibration_ratio,
            min_validation_coverage=args.min_validation_coverage,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
