"""Aggregate readiness report for the local architecture diagram demo."""

from __future__ import annotations

import argparse
import json

from src.hackaithon_mvp.dag_forecast_output_verification import run_dag_forecast_verification_cases
from src.hackaithon_mvp.dashboard_artifact_export import build_dashboard_artifact, validate_dashboard_artifact
from src.hackaithon_mvp.decision_lane_v2 import run_decision_lane_v2
from src.hackaithon_mvp.diagnostic_engine_hardening_gate import run_diagnostic_engine_hardening_gate
from src.hackaithon_mvp.diagram_coverage_matrix import build_diagram_coverage_matrix, summarize_diagram_coverage
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture, validate_engine_input_payload
from src.hackaithon_mvp.feedback_loop_contract import (
    build_feedback_loop_contract,
    build_policy_update_candidate,
    validate_feedback_loop_boundary,
)
from src.hackaithon_mvp.ml_diagnostic_engine import run_ml_diagnostic_engine
from src.hackaithon_mvp.periodic_diagnostic_runner import build_periodic_runner_plan
from src.hackaithon_mvp.public_architecture_alignment import (
    audit_architecture_alignment_claims,
    build_public_architecture_alignment,
)
from src.hackaithon_mvp.risk_engine_v2 import run_risk_engine_v2
from src.hackaithon_mvp.scenario_engine_v2 import run_scenario_engine_v2
from src.hackaithon_mvp.social_listening_contract import (
    build_empty_social_context,
    get_social_listening_contract,
)


NON_CLAIM_TEXT = "Diagram demo readiness is local/static and requires human review."
CLAIM_BOUNDARY = {
    "local_static_demo_only": True,
    "writes_files": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "no_server_database": True,
    "no_dashboard_web_app": True,
    "human_review_required": True,
}


def build_diagram_demo_readiness_summary() -> dict:
    """Aggregate Level 1 and Level 2 readiness into one summary."""

    dag_verification = run_dag_forecast_verification_cases()
    matrix = build_diagram_coverage_matrix()
    coverage_summary = summarize_diagram_coverage(matrix)
    architecture_alignment = build_public_architecture_alignment()
    architecture_audit = audit_architecture_alignment_claims(architecture_alignment)
    periodic_plan = build_periodic_runner_plan()
    dashboard_artifact = build_dashboard_artifact(
        readiness_summary={"readiness_status": "local_diagram_demo_review"},
        coverage_summary=coverage_summary,
    )
    dashboard_validation = validate_dashboard_artifact(dashboard_artifact)
    social_contract = get_social_listening_contract()
    social_context = build_empty_social_context()
    feedback_contract = build_feedback_loop_contract()
    feedback_candidate = build_policy_update_candidate(
        evaluation_summary={
            "evaluation_status": "missing",
            "directional_accuracy": None,
            "coverage_ratio": None,
        },
        current_policy_id=None,
    )
    feedback_validation = validate_feedback_loop_boundary(feedback_candidate)
    engine_payload = build_minimal_engine_input_fixture()
    input_validation = validate_engine_input_payload(engine_payload)
    ml_summary = run_ml_diagnostic_engine(tuple(engine_payload["model_diagnostics"]))
    scenario_summary = run_scenario_engine_v2(payload=engine_payload, ml_summary=ml_summary)
    risk_summary = run_risk_engine_v2(payload=engine_payload, ml_summary=ml_summary, scenario_summary=scenario_summary)
    decision_summary = run_decision_lane_v2(
        diagnostic_output={"forecast_diagnostic": engine_payload["forecast_rows"][0]["forecast_diagnostic"]},
        ml_summary=ml_summary,
        risk_summary=risk_summary,
        scenario_summary=scenario_summary,
    )
    hardening_gate = run_diagnostic_engine_hardening_gate()

    checks = {
        "dag_forecast_verification": dag_verification.get("verification_status") == "completed",
        "diagram_coverage_matrix": coverage_summary.get("coverage_status") == "complete",
        "architecture_alignment": architecture_audit.get("is_safe") is True,
        "periodic_runner_contract": periodic_plan.get("dry_run_default") is True,
        "dashboard_artifact_export": dashboard_validation.get("is_valid") is True,
        "social_listening_contract": social_contract.get("contract_status") == "schema_contract_only",
        "feedback_loop_contract": feedback_validation.get("is_valid") is True,
        "gateway_input_contract_ready": input_validation.get("is_valid") is True,
        "ml_diagnostic_engine_ready": ml_summary.get("ml_engine_status") == "completed",
        "scenario_engine_v2_ready": scenario_summary.get("scenario_engine_status") == "completed",
        "risk_engine_v2_ready": risk_summary.get("risk_engine_status") == "completed",
        "decision_lane_v2_ready": decision_summary.get("decision_lane_status") == "routed_for_review",
        "hardening_gate_ready": hardening_gate.get("hardening_status") == "accepted_for_gateway_ready_local_engine_core",
    }
    ready = all(checks.values())
    return {
        "readiness_status": "ready_for_local_diagram_demo_after_human_review" if ready else "attention_required",
        "checks": checks,
        "dag_forecast_verification_summary": {
            "case_count": dag_verification.get("case_count"),
            "completed_case_count": dag_verification.get("completed_case_count"),
            "non_directional_preserved_count": dag_verification.get("non_directional_preserved_count"),
            "warning_count": dag_verification.get("warning_count"),
        },
        "diagram_coverage_matrix_summary": coverage_summary,
        "architecture_alignment_status": architecture_alignment.get("alignment_status"),
        "architecture_alignment_audit": architecture_audit,
        "periodic_runner_contract_status": periodic_plan.get("plan_status"),
        "dashboard_artifact_export_status": "valid" if dashboard_validation.get("is_valid") else "invalid",
        "social_listening_contract_status": social_contract.get("contract_status"),
        "social_context_status": social_context.get("context_status"),
        "feedback_loop_contract_status": feedback_contract.get("contract_status"),
        "feedback_candidate_action": feedback_candidate.get("candidate_action"),
        "gateway_input_contract_ready": checks["gateway_input_contract_ready"],
        "ml_diagnostic_engine_ready": checks["ml_diagnostic_engine_ready"],
        "risk_engine_v2_ready": checks["risk_engine_v2_ready"],
        "scenario_engine_v2_ready": checks["scenario_engine_v2_ready"],
        "decision_lane_v2_ready": checks["decision_lane_v2_ready"],
        "hardening_gate_status": hardening_gate.get("hardening_status"),
        "remaining_future_scope": architecture_alignment.get("future_scope", []),
        "explicitly_excluded": architecture_alignment.get("explicitly_excluded", []),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_diagram_demo_readiness_report(summary: dict) -> str:
    """Render a compact public-safe diagram demo readiness report."""

    coverage = summary.get("diagram_coverage_matrix_summary", {})
    dag_summary = summary.get("dag_forecast_verification_summary", {})
    lines = [
        "# Diagram Demo Readiness",
        "",
        f"Readiness status: {summary.get('readiness_status')}",
        "",
        "## DAG Forecast Verification",
        f"Cases: {dag_summary.get('completed_case_count')} of {dag_summary.get('case_count')}",
        f"Policy preserved non-directional states: {dag_summary.get('non_directional_preserved_count')}",
        "",
        "## Diagram Coverage",
        f"Coverage status: {coverage.get('coverage_status')}",
        f"Block count: {coverage.get('block_count')} of {coverage.get('required_block_count')}",
        f"Status counts: {json.dumps(coverage.get('status_counts', {}), sort_keys=True)}",
        "",
        "## Local Contracts",
        f"Architecture alignment: {summary.get('architecture_alignment_status')}",
        f"Periodic runner: {summary.get('periodic_runner_contract_status')}",
        f"Dashboard artifact export: {summary.get('dashboard_artifact_export_status')}",
        f"Social listening: {summary.get('social_listening_contract_status')}",
        f"Feedback loop: {summary.get('feedback_loop_contract_status')}",
        "",
        "## Diagnostic Engine Core",
        f"Gateway input contract ready: {summary.get('gateway_input_contract_ready')}",
        f"ML Diagnostic Engine ready: {summary.get('ml_diagnostic_engine_ready')}",
        f"Scenario Engine V2 ready: {summary.get('scenario_engine_v2_ready')}",
        f"Risk Engine V2 ready: {summary.get('risk_engine_v2_ready')}",
        f"Decision Lane V2 ready: {summary.get('decision_lane_v2_ready')}",
        f"Hardening gate status: {summary.get('hardening_gate_status')}",
        "",
        "## Future Scope",
        *[f"- {item}" for item in summary.get("remaining_future_scope", [])],
        "",
        "## Boundary",
        "Local/static diagram demo readiness only; no files are written.",
        "No operational decisions are produced.",
        "Human review remains required.",
        str(summary.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate local diagram demo readiness.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    summary = build_diagram_demo_readiness_summary()
    if args.format == "report":
        print(render_diagram_demo_readiness_report(summary), end="")
    else:
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary.get("readiness_status") == "ready_for_local_diagram_demo_after_human_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
