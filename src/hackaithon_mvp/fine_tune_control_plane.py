"""Fine-tune control plane for human-review experiment candidates only."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.dag_backtest_harness import build_dag_backtest_fixture, run_dag_backtest_from_payloads
from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture


CLAIM_BOUNDARY = {
    "fine_tune_control_plane_only": True,
    "experiment_candidate_only": True,
    "no_training": True,
    "no_external_model_calls": True,
    "no_provider_calls": True,
    "no_inference": True,
    "no_auto_policy_mutation": True,
    "auto_training_allowed": False,
    "auto_deploy_allowed": False,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Fine-tune control plane creates human-review experiment candidates only; no training is performed."
ALLOWED_ACTIONS = (
    "review_thresholds",
    "review_feature_sets",
    "review_policy_gate",
    "collect_more_evidence",
    "insufficient_data_for_fine_tune",
)


def build_fine_tune_control_policy() -> dict:
    """Build the deterministic fine-tune control policy."""

    return {
        "policy_version": "1.0",
        "policy_status": "control_plane_ready",
        "allowed_candidate_actions": list(ALLOWED_ACTIONS),
        "auto_training_allowed": False,
        "auto_deploy_allowed": False,
        "provider_calls_allowed": False,
        "human_review_required": True,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def assess_fine_tune_readiness(
    *,
    engine_result: dict | None = None,
    backtest_result: dict | None = None,
    ml_summary: dict | None = None,
) -> dict:
    """Assess whether a human-review experiment candidate can be drafted."""

    required_inputs = ["engine_result", "backtest_result", "ml_summary"]
    blocking_reasons: list[str] = []
    if engine_result is None:
        blocking_reasons.append("engine_result_required")
    if backtest_result is None:
        blocking_reasons.append("backtest_result_required")
    if ml_summary is None:
        blocking_reasons.append("ml_summary_required")
    model_count = int((ml_summary or {}).get("model_count", 0) or 0)
    backtest_runs = int((backtest_result or {}).get("engine_run_count", 0) or 0)
    engine_complete = str((engine_result or {}).get("engine_status", "")).startswith("completed")
    if ml_summary is not None and model_count < 2:
        blocking_reasons.append("more_model_diagnostic_evidence_required")
    if backtest_result is not None and backtest_runs < 1:
        blocking_reasons.append("local_harness_runs_required")
    if engine_result is not None and not engine_complete:
        blocking_reasons.append("completed_engine_result_required")

    if not (engine_result or backtest_result or ml_summary):
        readiness_level = "not_ready"
    elif any(reason.endswith("_required") for reason in blocking_reasons):
        readiness_level = "data_required"
    elif blocking_reasons:
        readiness_level = "review_required"
    else:
        readiness_level = "candidate_ready"

    readiness = {
        "fine_tune_status": "assessed",
        "readiness_level": readiness_level,
        "required_inputs": required_inputs,
        "blocking_reasons": list(dict.fromkeys(blocking_reasons)),
        "candidate": None,
        "human_review_required": True,
        "auto_training_allowed": False,
        "auto_deploy_allowed": False,
        "provider_calls_allowed": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }
    return readiness


def build_fine_tune_experiment_candidate(
    *,
    readiness: dict,
    candidate_name: str = "diagnostic_policy_review_candidate",
) -> dict:
    """Draft a fine-tune experiment candidate for human review only."""

    readiness_level = str((readiness or {}).get("readiness_level", "not_ready"))
    blocking = list((readiness or {}).get("blocking_reasons", []) or [])
    if readiness_level == "candidate_ready":
        actions = ["review_thresholds", "review_feature_sets", "review_policy_gate"]
    elif readiness_level == "review_required":
        actions = ["review_policy_gate", "collect_more_evidence"]
    else:
        actions = ["collect_more_evidence", "insufficient_data_for_fine_tune"]
    return {
        "candidate_name": str(candidate_name or "diagnostic_policy_review_candidate"),
        "candidate_status": "draft_for_human_review",
        "readiness_level": readiness_level,
        "recommended_review_actions": actions,
        "blocking_reasons": blocking,
        "human_review_required": True,
        "auto_training_allowed": False,
        "auto_deploy_allowed": False,
        "provider_calls_allowed": False,
        "policy_mutation_allowed": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def validate_fine_tune_candidate(candidate: dict) -> dict:
    """Validate a fine-tune experiment candidate boundary."""

    errors: list[str] = []
    if not isinstance(candidate, dict):
        return {
            "is_valid": False,
            "errors": ["candidate must be an object"],
            "warnings": [],
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }
    if candidate.get("human_review_required") is not True:
        errors.append("human_review_required must be True")
    for field in ("auto_training_allowed", "auto_deploy_allowed", "provider_calls_allowed", "policy_mutation_allowed"):
        if candidate.get(field) is not False:
            errors.append(f"{field} must be False")
    for action in candidate.get("recommended_review_actions", []) or []:
        if action not in ALLOWED_ACTIONS:
            errors.append(f"unrecognized candidate action: {action}")
    boundary = candidate.get("claim_boundary", {})
    for key, expected in CLAIM_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"claim_boundary.{key} must be {expected}")
    return {
        "is_valid": not errors,
        "errors": errors,
        "warnings": [],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_fine_tune_control_report(readiness: dict, candidate: dict) -> str:
    """Render a compact fine-tune control plane report."""

    lines = [
        "# Fine-tune Control Plane",
        "",
        f"Fine-tune status: {readiness.get('fine_tune_status')}",
        f"Readiness level: {readiness.get('readiness_level')}",
        f"Candidate status: {candidate.get('candidate_status')}",
        f"Recommended review actions: {', '.join(candidate.get('recommended_review_actions', []))}",
        "Human review required: True",
        "Auto training allowed: False",
        "Auto deploy allowed: False",
        "Provider calls allowed: False",
        "",
        "## Boundary",
        "Experiment-candidate control plane only; no training, external model calls, inference, or automatic policy mutation.",
        str(readiness.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _demo_readiness() -> tuple[dict, dict]:
    payload = build_minimal_engine_input_fixture()
    engine_result = run_diagnostic_engine_from_payload(payload)
    backtest = run_dag_backtest_from_payloads(payloads=tuple(build_dag_backtest_fixture()["payloads"]))
    readiness = assess_fine_tune_readiness(
        engine_result=engine_result,
        backtest_result=backtest,
        ml_summary=engine_result.get("ml_engine"),
    )
    candidate = build_fine_tune_experiment_candidate(readiness=readiness)
    return readiness, candidate


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect fine-tune control plane readiness.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    readiness, candidate = _demo_readiness()
    output = {
        "readiness": readiness,
        "candidate": candidate,
        "validation": validate_fine_tune_candidate(candidate),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }
    if args.format == "report":
        print(render_fine_tune_control_report(readiness, candidate), end="")
    else:
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
