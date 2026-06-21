"""Decision Lane V2: final diagnostic routing for human review."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.engine_input_contract import CLAIM_BOUNDARY as INPUT_CLAIM_BOUNDARY, build_minimal_engine_input_fixture
from src.hackaithon_mvp.ml_diagnostic_engine import run_ml_diagnostic_engine
from src.hackaithon_mvp.risk_engine_v2 import run_risk_engine_v2
from src.hackaithon_mvp.scenario_engine_v2 import run_scenario_engine_v2


CLAIM_BOUNDARY = {
    **INPUT_CLAIM_BOUNDARY,
    "diagnostic_routing_only": True,
    "auto_execution_allowed": False,
}
NON_CLAIM_TEXT = "Diagnostic routing only; human review required."
DECISION_LANES = (
    "standard_human_review",
    "evidence_insufficient_review",
    "risk_review_required",
    "policy_review_required",
    "calibration_review_required",
    "blocked_pending_evidence",
    "blocked_pending_risk_review",
)


def build_decision_lane_v2_policy() -> dict:
    """Build deterministic routing policy for Decision Lane V2."""

    return {
        "policy_version": "2.0",
        "decision_lanes": list(DECISION_LANES),
        "rules": [
            "critical risk blocks pending risk review",
            "insufficient evidence routes to evidence review or evidence block",
            "policy gate states do not upgrade non-directional diagnostics",
            "model disagreement requires risk review",
            "human review is always required",
        ],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _forecast_diagnostic(diagnostic_output: dict[str, Any]) -> str:
    return str(
        diagnostic_output.get("forecast_diagnostic")
        or diagnostic_output.get("quant_signal")
        or "insufficient_evidence"
    )


def _policy_status(diagnostic_output: dict[str, Any], ml_summary: dict[str, Any]) -> str:
    policy_values = [
        diagnostic_output.get("policy_runtime_status"),
        diagnostic_output.get("policy_metadata", {}).get("policy_runtime_status")
        if isinstance(diagnostic_output.get("policy_metadata"), dict)
        else None,
    ]
    validation = (ml_summary or {}).get("validation", {})
    records = validation.get("normalized_records", ()) if isinstance(validation, dict) else ()
    for row in records or ():
        if isinstance(row, dict) and row.get("policy_runtime_status"):
            policy_values.append(row.get("policy_runtime_status"))
    return next((str(value).strip() for value in policy_values if value not in (None, "")), "policy_not_applied")


def _priority(lane: str, risk_level: str) -> str:
    if lane in {"blocked_pending_risk_review", "blocked_pending_evidence"} or risk_level == "critical":
        return "critical"
    if lane in {"risk_review_required", "policy_review_required"} or risk_level == "high":
        return "high"
    if lane == "calibration_review_required" or risk_level == "medium":
        return "medium"
    return "low"


def run_decision_lane_v2(
    *,
    diagnostic_output: dict,
    ml_summary: dict,
    risk_summary: dict,
    scenario_summary: dict,
) -> dict:
    """Route final diagnostic output to a human-review lane."""

    diagnostic = _forecast_diagnostic(diagnostic_output or {})
    risk_level = str((risk_summary or {}).get("risk_level", "critical"))
    agreement = str((ml_summary or {}).get("agreement_status", "insufficient_models"))
    ml_lane = str((ml_summary or {}).get("recommended_review_lane", "evidence_insufficient_review"))
    calibration = str((ml_summary or {}).get("calibration_status", "missing"))
    policy_status = _policy_status(diagnostic_output or {}, ml_summary or {})
    stability = str((scenario_summary or {}).get("stability_status", "uncertain"))
    blocking_reasons: list[str] = []
    required_reviews = ["human_review"]

    if risk_level == "critical":
        lane = "blocked_pending_risk_review"
        blocking_reasons.append("critical_risk")
        required_reviews.append("risk_review")
    elif diagnostic == "insufficient_evidence":
        if risk_level == "high" or stability == "insufficient_evidence":
            lane = "blocked_pending_evidence"
            blocking_reasons.append("insufficient_evidence")
        else:
            lane = "evidence_insufficient_review"
        required_reviews.append("evidence_review")
    elif policy_status in {"policy_review_required", "policy_invalid"} or ml_lane == "policy_review_required":
        lane = "policy_review_required"
        required_reviews.append("policy_review")
    elif agreement == "high_disagreement" or ml_lane == "risk_review_required":
        lane = "risk_review_required"
        required_reviews.append("risk_review")
    elif calibration in {"weak", "uncalibrated", "calibration_review_required"} or ml_lane == "calibration_review_required":
        lane = "calibration_review_required"
        required_reviews.append("calibration_review")
    elif risk_level == "high":
        lane = "risk_review_required"
        required_reviews.append("risk_review")
    elif ml_lane == "evidence_insufficient_review":
        lane = "evidence_insufficient_review"
        required_reviews.append("evidence_review")
    else:
        lane = "standard_human_review"

    if policy_status in {"downgraded_to_uncertain", "non_directional_preserved"}:
        blocking_reasons.append("policy_gate_non_directional_preserved")
        if lane == "standard_human_review":
            required_reviews.append("policy_review")

    if lane not in DECISION_LANES:
        raise ValueError(f"unsupported Decision Lane V2 lane: {lane}")
    priority = _priority(lane, risk_level)
    status = "blocked_for_review" if lane.startswith("blocked_") else "routed_for_review"
    return {
        "decision_lane_status": status,
        "lane": lane,
        "review_priority": priority,
        "required_reviews": list(dict.fromkeys(required_reviews)),
        "blocking_reasons": list(dict.fromkeys(blocking_reasons)),
        "human_review_required": True,
        "auto_execution_allowed": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Decision Lane V2 on a deterministic local fixture.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def _render_report(result: dict) -> str:
    lines = [
        "# Decision Lane V2",
        "",
        f"Status: {result.get('decision_lane_status')}",
        f"Lane: {result.get('lane')}",
        f"Review priority: {result.get('review_priority')}",
        f"Required reviews: {', '.join(result.get('required_reviews', []))}",
        f"Blocking reasons: {', '.join(result.get('blocking_reasons', []) or ['none'])}",
        "Human review required: True",
        "Auto execution allowed: False",
        "",
        "Boundary: diagnostic routing only; no live data, provider calls, training, inference, or benchmark rerun.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    fixture = build_minimal_engine_input_fixture()
    ml_summary = run_ml_diagnostic_engine(tuple(fixture["model_diagnostics"]))
    scenario = run_scenario_engine_v2(payload=fixture, ml_summary=ml_summary)
    risk = run_risk_engine_v2(payload=fixture, ml_summary=ml_summary, scenario_summary=scenario)
    diagnostic_output = {"forecast_diagnostic": "neutral_or_uncertain"}
    result = run_decision_lane_v2(
        diagnostic_output=diagnostic_output,
        ml_summary=ml_summary,
        risk_summary=risk,
        scenario_summary=scenario,
    )
    if args.format == "report":
        print(_render_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
