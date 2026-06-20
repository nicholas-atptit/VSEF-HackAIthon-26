"""Calibration gate for Quant Core forecast diagnostic rows."""

from __future__ import annotations

from typing import Any

from src.hackaithon_mvp.forecast_actual_evaluation import DIRECTIONAL_DIAGNOSTICS
from src.hackaithon_mvp.quant_core_performance_attribution import NON_CLAIM_TEXT


MATCH_FIELD_PRIORITY = ("ticker", "timeframe", "horizon_steps", "model_family", "model_key", "engine_id")


def _normalize_match_value(field: str, value: Any) -> str | None:
    if value in (None, ""):
        return None
    if field == "ticker":
        return str(value).strip().upper()
    if field == "horizon_steps":
        return str(int(value))
    return str(value).strip()


def _group_match_score(forecast_row: dict, group_key: dict[str, Any]) -> int | None:
    matched = 0
    for field in MATCH_FIELD_PRIORITY:
        if field not in group_key:
            continue
        policy_value = _normalize_match_value(field, group_key.get(field))
        if policy_value is None or policy_value == "unspecified":
            continue
        row_value = _normalize_match_value(field, forecast_row.get(field))
        if row_value != policy_value:
            return None
        matched += 1
    return matched if matched > 0 else None


def _gate_reason(group: dict | None) -> str:
    if group is None:
        return "no_matching_calibrated_group"
    if not group.get("is_sample_sufficient", False):
        return "insufficient_sample_count"
    if group.get("balanced_directional_accuracy") is None:
        return "balanced_accuracy_unavailable"
    if group.get("is_weak_group", False):
        return "weak_historical_slice"
    if not group.get("is_directionally_eligible", False):
        return "below_min_balanced_accuracy"
    return "eligible_historical_slice"


def build_calibration_gate_policy(
    attribution: dict,
    min_balanced_accuracy: float = 0.525,
    strong_balanced_accuracy: float = 0.55,
    min_sample_count: int = 30,
) -> dict:
    """Convert attribution groups into a deterministic diagnostic gate policy."""

    rules = []
    for group in attribution.get("groups", ()):
        sample_count = int(group.get("sample_count", 0))
        balanced_accuracy = group.get("balanced_directional_accuracy")
        sample_sufficient = sample_count >= min_sample_count
        directionally_eligible = (
            sample_sufficient
            and balanced_accuracy is not None
            and float(balanced_accuracy) >= min_balanced_accuracy
        )
        is_strong = (
            sample_sufficient
            and balanced_accuracy is not None
            and float(balanced_accuracy) >= strong_balanced_accuracy
        )
        is_weak = sample_sufficient and balanced_accuracy is not None and float(balanced_accuracy) < 0.50
        rules.append(
            {
                "match": dict(group.get("group_key", {})),
                "group_key_id": group.get("group_key_id"),
                "sample_count": sample_count,
                "balanced_directional_accuracy": balanced_accuracy,
                "directional_accuracy": group.get("directional_accuracy"),
                "is_sample_sufficient": sample_sufficient,
                "is_directionally_eligible": directionally_eligible,
                "is_strong_group": is_strong,
                "is_weak_group": is_weak,
            }
        )
    return {
        "min_balanced_accuracy": min_balanced_accuracy,
        "strong_balanced_accuracy": strong_balanced_accuracy,
        "min_sample_count": min_sample_count,
        "group_fields": tuple(attribution.get("group_fields", ())),
        "rules": sorted(rules, key=lambda rule: str(rule.get("group_key_id"))),
        "eligible_group_count": len([rule for rule in rules if rule["is_directionally_eligible"]]),
        "weak_group_count": len([rule for rule in rules if rule["is_weak_group"]]),
        "strong_group_count": len([rule for rule in rules if rule["is_strong_group"]]),
        "non_claim": NON_CLAIM_TEXT,
    }


def _best_matching_rule(forecast_row: dict, policy: dict) -> dict | None:
    matches: list[tuple[int, dict]] = []
    for rule in policy.get("rules", ()):
        score = _group_match_score(forecast_row, rule.get("match", {}))
        if score is not None:
            matches.append((score, rule))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1].get("sample_count", 0)), reverse=True)
    return matches[0][1]


def apply_calibration_gate(
    forecast_row: dict,
    policy: dict,
) -> dict:
    """Apply a historical calibration gate to one Quant Core forecast row."""

    gated = dict(forecast_row)
    diagnostic = str(gated.get("forecast_diagnostic", "")).strip()
    matched_rule = _best_matching_rule(gated, policy)
    gated["matched_gate_group"] = matched_rule.get("group_key_id") if matched_rule else None
    gated["gate_reason"] = _gate_reason(matched_rule)
    if diagnostic not in DIRECTIONAL_DIAGNOSTICS:
        gated["gate_status"] = "non_directional_preserved"
        return gated
    if matched_rule is not None and matched_rule.get("is_directionally_eligible") is True:
        gated["gate_status"] = "directional_allowed"
        return gated
    gated["forecast_diagnostic"] = "neutral_or_uncertain"
    gated["gate_status"] = "downgraded_to_uncertain"
    return gated
