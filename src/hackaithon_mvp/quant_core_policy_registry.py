"""Versioned Quant Core diagnostic policy registry objects."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any


POLICY_VERSION = "1.0"
CREATED_FOR = "quant_core_runtime_policy_application"
NON_CLAIM_TEXT = "Diagnostic research policy object; validation split metrics are local policy-simulation evidence only."
CLAIM_BOUNDARY = {
    "validation_split_policy_simulation": True,
    "not_training_result": True,
    "not_inference_result": True,
    "not_benchmark_rerun": True,
    "not_production_performance_claim": True,
    "human_review_required": True,
}
FORBIDDEN_PUBLIC_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\bfinancial advice\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bsupport(?:ed|s|ing)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bdeployment\b",
    r"\bapproval\b",
    r"\bclient relationship\b",
)


def _safe_float(value: Any, field_name: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if number != number:
        raise ValueError(f"{field_name} must be numeric")
    return round(number, 6)


def _normalize_group(group: dict[str, Any]) -> dict[str, str]:
    if not isinstance(group, dict):
        raise ValueError("eligible group must be a dictionary")
    normalized: dict[str, str] = {}
    for key, value in group.items():
        if value in (None, ""):
            continue
        normalized[str(key)] = str(value).strip()
    if not normalized:
        raise ValueError("eligible group must include at least one match key")
    return dict(sorted(normalized.items()))


def _contains_forbidden_text(payload: dict) -> list[str]:
    text = json.dumps(payload, sort_keys=True).lower()
    return [pattern for pattern in FORBIDDEN_PUBLIC_PATTERNS if re.search(pattern, text)]


def build_policy_registry_entry(
    *,
    policy_id: str,
    policy_name: str,
    policy_type: str,
    source_dataset_id: str,
    validation_accuracy: float,
    validation_balanced_accuracy: float,
    validation_coverage: float,
    eligible_groups: tuple[dict, ...],
    warnings: tuple[str, ...] = (),
) -> dict:
    """Build a small JSON-compatible Quant Core policy registry object."""

    validation_accuracy = _safe_float(validation_accuracy, "validation_accuracy")
    validation_balanced_accuracy = _safe_float(validation_balanced_accuracy, "validation_balanced_accuracy")
    validation_coverage = _safe_float(validation_coverage, "validation_coverage")
    if validation_coverage <= 0:
        raise ValueError("validation_coverage must be positive")
    groups = tuple(_normalize_group(group) for group in eligible_groups)
    return {
        "policy_id": str(policy_id).strip(),
        "policy_name": str(policy_name).strip(),
        "policy_type": str(policy_type).strip(),
        "policy_version": POLICY_VERSION,
        "source_dataset_id": str(source_dataset_id).strip(),
        "created_for": CREATED_FOR,
        "validation_metrics": {
            "validation_accuracy": validation_accuracy,
            "validation_balanced_accuracy": validation_balanced_accuracy,
            "validation_coverage": validation_coverage,
        },
        "coverage_tradeoff": {
            "validation_coverage": validation_coverage,
            "coverage_dependent": validation_coverage < 1.0,
            "low_coverage": validation_coverage < 0.20,
        },
        "eligible_group_count": len(groups),
        "eligible_groups": list(groups),
        "warnings": list(dict.fromkeys(str(item) for item in warnings)),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def validate_policy_registry_entry(policy: dict) -> dict:
    """Validate a versioned Quant Core policy registry object."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(policy, dict):
        return {"is_valid": False, "errors": ["policy must be a dictionary"], "warnings": []}
    if not str(policy.get("policy_id", "")).strip():
        errors.append("policy_id must be non-empty")
    groups = policy.get("eligible_groups")
    if not isinstance(groups, list):
        errors.append("eligible_groups must be a list")
    elif not groups:
        warnings.append("eligible_groups is empty")
    elif not all(isinstance(group, dict) and group for group in groups):
        errors.append("eligible_groups must contain non-empty dictionaries")

    metrics = policy.get("validation_metrics")
    if not isinstance(metrics, dict):
        errors.append("validation_metrics must be present")
    else:
        for field in ("validation_accuracy", "validation_balanced_accuracy", "validation_coverage"):
            try:
                value = _safe_float(metrics.get(field), field)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if field == "validation_coverage" and value <= 0:
                errors.append("validation_coverage must be positive")

    forbidden = _contains_forbidden_text(policy)
    if forbidden:
        errors.append(f"forbidden public wording found: {', '.join(forbidden)}")
    return {"is_valid": not errors, "errors": errors, "warnings": warnings}


def get_demo_policy_predicted_vs_actual() -> dict:
    """Return a tiny representative policy fixture for the verified return-magnitude artifact."""

    return build_policy_registry_entry(
        policy_id="quant_core_policy.pva.eligible_slice_gate.v1",
        policy_name="eligible_slice_gate_bacc_0.600",
        policy_type="eligible_slice_gate",
        source_dataset_id="legacy_predicted_vs_actual_validation_split",
        validation_accuracy=0.534888,
        validation_balanced_accuracy=0.532707,
        validation_coverage=0.16269,
        eligible_groups=(
            {"ticker": "AAA", "timeframe": "1h", "horizon_steps": 40, "model_family": "tree_a"},
            {"ticker": "BBB", "timeframe": "1h", "horizon_steps": 40, "model_family": "tree_b"},
        ),
        warnings=("large_coverage_reduction",),
    )


def get_demo_policy_h40_direction_only() -> dict:
    """Return a tiny representative policy fixture for the verified h40 direction-only artifact."""

    return build_policy_registry_entry(
        policy_id="quant_core_policy.h40.eligible_slice_gate.v1",
        policy_name="eligible_slice_gate_bacc_0.500",
        policy_type="eligible_slice_gate",
        source_dataset_id="legacy_h40_direction_only_validation_split",
        validation_accuracy=0.738202,
        validation_balanced_accuracy=0.68537,
        validation_coverage=0.546012,
        eligible_groups=(
            {"ticker": "AAA", "timeframe": "1h", "horizon_steps": 40, "model_family": "linear_a"},
            {"ticker": "BBB", "timeframe": "1h", "horizon_steps": 40, "model_family": "linear_a"},
        ),
        warnings=("direction_only_legacy_evidence",),
    )


def _demo_policies() -> dict[str, dict]:
    return {
        "predicted_vs_actual": get_demo_policy_predicted_vs_actual(),
        "h40": get_demo_policy_h40_direction_only(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect built-in Quant Core diagnostic policy fixtures.")
    parser.add_argument("--list-demo", action="store_true")
    parser.add_argument("--show-demo", choices=("predicted_vs_actual", "h40"), default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    demos = _demo_policies()
    if args.list_demo:
        output: dict[str, Any] = {"demo_policies": sorted(demos)}
    elif args.show_demo:
        output = demos[args.show_demo]
    else:
        parser.error("use --list-demo or --show-demo")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
