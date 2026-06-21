"""Local feedback loop contract for evaluation-to-review candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any


ALLOWED_CANDIDATE_ACTIONS = (
    "keep_policy",
    "review_thresholds",
    "review_slice_eligibility",
    "insufficient_evidence",
)
NON_CLAIM_TEXT = "Feedback loop contract creates human-review candidates only."
CLAIM_BOUNDARY = {
    "contract_only": True,
    "auto_apply_allowed": False,
    "automatic_policy_update": False,
    "training_triggered": False,
    "inference_triggered": False,
    "benchmark_rerun": False,
    "live_data_enabled": False,
    "provider_calls_enabled": False,
    "human_review_required": True,
}


def build_feedback_loop_contract() -> dict:
    """Build the local feedback loop boundary contract."""

    return {
        "contract_status": "human_review_candidate_contract",
        "allowed_candidate_action": list(ALLOWED_CANDIDATE_ACTIONS),
        "evaluation_input_required": True,
        "auto_apply_allowed": False,
        "automatic_policy_update": False,
        "training_triggered": False,
        "inference_triggered": False,
        "benchmark_rerun": False,
        "live_data_enabled": False,
        "provider_calls_enabled": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _candidate_action(evaluation_summary: dict[str, Any]) -> str:
    status = str(
        evaluation_summary.get("evaluation_status")
        or evaluation_summary.get("actual_data_status")
        or "missing"
    )
    accuracy = evaluation_summary.get("directional_accuracy")
    coverage = evaluation_summary.get("coverage_ratio")
    if status not in {"completed", "provided"} or accuracy is None or coverage is None:
        return "insufficient_evidence"
    try:
        accuracy_value = float(accuracy)
        coverage_value = float(coverage)
    except (TypeError, ValueError):
        return "insufficient_evidence"
    if coverage_value < 0.2:
        return "review_slice_eligibility"
    if accuracy_value < 0.5:
        return "review_thresholds"
    return "keep_policy"


def _candidate_id(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return "feedback-candidate-" + hashlib.sha256(encoded).hexdigest()[:12]


def build_policy_update_candidate(
    *,
    evaluation_summary: dict,
    current_policy_id: str | None = None,
) -> dict:
    """Build a human-review policy update candidate from local evaluation metrics."""

    action = _candidate_action(dict(evaluation_summary or {}))
    base = {
        "current_policy_id": current_policy_id,
        "evaluation_status": evaluation_summary.get("evaluation_status")
        or evaluation_summary.get("actual_data_status")
        or "missing",
        "observed_directional_accuracy": evaluation_summary.get("directional_accuracy"),
        "observed_coverage_ratio": evaluation_summary.get("coverage_ratio"),
        "candidate_action": action,
    }
    return {
        "candidate_id": _candidate_id(base),
        **base,
        "requires_human_review": True,
        "auto_apply_allowed": False,
        "training_triggered": False,
        "inference_triggered": False,
        "benchmark_rerun": False,
        "live_data_used": False,
        "provider_calls_used": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def validate_feedback_loop_boundary(candidate: dict) -> dict:
    """Validate feedback loop candidate safety boundaries."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(candidate, dict):
        return {"is_valid": False, "errors": ["candidate must be a dictionary"], "warnings": []}
    for field in (
        "candidate_id",
        "current_policy_id",
        "evaluation_status",
        "observed_directional_accuracy",
        "observed_coverage_ratio",
        "candidate_action",
        "requires_human_review",
        "auto_apply_allowed",
        "training_triggered",
        "inference_triggered",
        "claim_boundary",
    ):
        if field not in candidate:
            errors.append(f"missing field: {field}")
    if candidate.get("candidate_action") not in ALLOWED_CANDIDATE_ACTIONS:
        errors.append("candidate_action is not allowed")
    if candidate.get("requires_human_review") is not True:
        errors.append("requires_human_review must be True")
    for field in (
        "auto_apply_allowed",
        "training_triggered",
        "inference_triggered",
        "benchmark_rerun",
        "live_data_used",
        "provider_calls_used",
    ):
        if candidate.get(field) is not False:
            errors.append(f"{field} must be False")
    boundary = candidate.get("claim_boundary", {})
    for key, expected in CLAIM_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"claim_boundary.{key} must be {expected}")
    if candidate.get("candidate_action") == "insufficient_evidence":
        warnings.append("candidate has insufficient local evaluation evidence")
    return {"is_valid": not errors, "errors": errors, "warnings": warnings}


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Inspect the feedback loop review-candidate contract.")


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    parser.parse_args(argv)
    candidate = build_policy_update_candidate(
        evaluation_summary={
            "evaluation_status": "missing",
            "directional_accuracy": None,
            "coverage_ratio": None,
        },
        current_policy_id=None,
    )
    print(
        json.dumps(
            {
                "contract": build_feedback_loop_contract(),
                "sample_candidate": candidate,
                "validation": validate_feedback_loop_boundary(candidate),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
