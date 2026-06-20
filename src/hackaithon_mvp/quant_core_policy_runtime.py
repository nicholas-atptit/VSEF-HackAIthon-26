"""Runtime application for registered Quant Core diagnostic policies."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.forecast_actual_evaluation import DIRECTIONAL_DIAGNOSTICS
from src.hackaithon_mvp.quant_core_policy_registry import (
    get_demo_policy_h40_direction_only,
    get_demo_policy_predicted_vs_actual,
    validate_policy_registry_entry,
)


NON_DIRECTIONAL_DIAGNOSTICS = {"neutral_or_uncertain", "insufficient_evidence", "exploratory_only"}
MATCH_KEYS = ("ticker", "timeframe", "horizon_steps", "model_family", "model_key", "engine_id")


def _normalize_match_value(key: str, value: Any) -> str | None:
    if value in (None, ""):
        return None
    if key == "ticker":
        return str(value).strip().upper()
    if key == "horizon_steps":
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return str(value).strip()
    return str(value).strip()


def _matches_group(forecast_row: dict, group: dict) -> bool:
    matched_any = False
    for key in MATCH_KEYS:
        if key not in group:
            continue
        expected = _normalize_match_value(key, group.get(key))
        if expected is None:
            continue
        actual = _normalize_match_value(key, forecast_row.get(key))
        if actual != expected:
            return False
        matched_any = True
    return matched_any


def _matching_group(forecast_row: dict, policy: dict) -> dict | None:
    for group in policy.get("eligible_groups", ()):
        if isinstance(group, dict) and _matches_group(forecast_row, group):
            return group
    return None


def apply_registered_policy_to_forecast(
    forecast_row: dict,
    policy: dict,
) -> dict:
    """Apply a registered policy to one forecast diagnostic row."""

    validation = validate_policy_registry_entry(policy)
    if not validation["is_valid"]:
        raise ValueError(f"invalid policy registry entry: {validation['errors']}")
    output = dict(forecast_row)
    original = str(output.get("forecast_diagnostic", "")).strip()
    metrics = policy["validation_metrics"]
    output.update(
        {
            "pre_policy_forecast_diagnostic": original,
            "policy_id": policy["policy_id"],
            "policy_name": policy["policy_name"],
            "policy_version": policy["policy_version"],
            "policy_validation_accuracy": metrics["validation_accuracy"],
            "policy_validation_balanced_accuracy": metrics["validation_balanced_accuracy"],
            "policy_validation_coverage": metrics["validation_coverage"],
        }
    )
    matching_group = _matching_group(output, policy)
    if original in NON_DIRECTIONAL_DIAGNOSTICS:
        output["policy_runtime_status"] = "non_directional_preserved"
        output["policy_runtime_reason"] = "non_directional_input_not_upgraded"
        return output
    if original in DIRECTIONAL_DIAGNOSTICS and matching_group is not None:
        output["policy_runtime_status"] = "directional_allowed"
        output["policy_runtime_reason"] = "matched_eligible_group"
        return output
    if original in DIRECTIONAL_DIAGNOSTICS:
        output["forecast_diagnostic"] = "neutral_or_uncertain"
        output["policy_runtime_status"] = "downgraded_to_uncertain"
        output["policy_runtime_reason"] = "no_matching_eligible_group"
        return output
    output["policy_runtime_status"] = "non_directional_preserved"
    output["policy_runtime_reason"] = "unknown_or_non_directional_input_not_upgraded"
    return output


def convert_registered_policy_to_gate_policy(policy: dict) -> dict:
    """Convert a registered eligible-group policy into calibration-gate shape."""

    validation = validate_policy_registry_entry(policy)
    if not validation["is_valid"]:
        return {
            "conversion_status": "not_convertible",
            "warnings": validation["errors"],
        }
    rules = []
    metrics = policy["validation_metrics"]
    for group in policy.get("eligible_groups", ()):
        rules.append(
            {
                "match": dict(group),
                "group_key_id": "|".join(f"{key}={value}" for key, value in sorted(group.items())),
                "sample_count": None,
                "balanced_directional_accuracy": metrics["validation_balanced_accuracy"],
                "directional_accuracy": metrics["validation_accuracy"],
                "is_sample_sufficient": True,
                "is_directionally_eligible": True,
                "is_strong_group": metrics["validation_balanced_accuracy"] >= 0.55,
                "is_weak_group": metrics["validation_balanced_accuracy"] < 0.50,
            }
        )
    return {
        "conversion_status": "converted",
        "policy": {
            "source_policy_id": policy["policy_id"],
            "source_policy_name": policy["policy_name"],
            "min_balanced_accuracy": None,
            "strong_balanced_accuracy": 0.55,
            "min_sample_count": None,
            "group_fields": tuple(MATCH_KEYS),
            "rules": rules,
            "eligible_group_count": len(rules),
            "weak_group_count": len([rule for rule in rules if rule["is_weak_group"]]),
            "strong_group_count": len([rule for rule in rules if rule["is_strong_group"]]),
        },
        "warnings": [],
    }


def _demo_policy(name: str) -> dict:
    if name == "predicted_vs_actual":
        return get_demo_policy_predicted_vs_actual()
    if name == "h40":
        return get_demo_policy_h40_direction_only()
    raise ValueError(f"unknown demo policy: {name}")


def _demo_forecast_for_policy(policy: dict) -> dict:
    group = policy["eligible_groups"][0]
    row = dict(group)
    row["forecast_diagnostic"] = "positive_bias"
    row["diagnostic_score"] = 0.75
    return row


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply a demo Quant Core registered policy to a sample row.")
    parser.add_argument("--demo", choices=("predicted_vs_actual", "h40"), required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        policy = _demo_policy(args.demo)
        output = {
            "policy": {
                "policy_id": policy["policy_id"],
                "policy_name": policy["policy_name"],
                "policy_version": policy["policy_version"],
            },
            "runtime_output": apply_registered_policy_to_forecast(_demo_forecast_for_policy(policy), policy),
        }
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
