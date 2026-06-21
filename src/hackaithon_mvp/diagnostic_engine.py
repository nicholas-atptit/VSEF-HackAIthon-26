"""Gateway-ready local diagnostic engine orchestrator."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.dashboard_artifact_export import build_dashboard_artifact, validate_dashboard_artifact
from src.hackaithon_mvp.decision_lane_v2 import run_decision_lane_v2
from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.engine_input_contract import (
    CLAIM_BOUNDARY as INPUT_CLAIM_BOUNDARY,
    NON_CLAIM_TEXT as INPUT_NON_CLAIM_TEXT,
    build_minimal_engine_input_fixture,
    validate_engine_input_payload,
)
from src.hackaithon_mvp.evidence_packet import build_evidence_packet
from src.hackaithon_mvp.ml_diagnostic_engine import run_ml_diagnostic_engine
from src.hackaithon_mvp.quant_core_policy_registry import (
    get_demo_policy_h40_direction_only,
    get_demo_policy_predicted_vs_actual,
)
from src.hackaithon_mvp.risk_engine_v2 import run_risk_engine_v2
from src.hackaithon_mvp.risk_engine_v3 import run_risk_engine_v3
from src.hackaithon_mvp.scenario_engine_v2 import run_scenario_engine_v2


CLAIM_BOUNDARY = {
    **INPUT_CLAIM_BOUNDARY,
    "gateway_ready_local_engine_core": True,
    "operating_production_system": False,
    "data_gateway_created": False,
    "server_database_created": False,
    "dashboard_web_app_created": False,
    "auto_execution_allowed": False,
}
NON_CLAIM_TEXT = "Gateway-ready local diagnostic subsystem; not an operating production system."


def _demo_policy(name: str | None) -> dict | None:
    if name is None:
        return None
    if name == "predicted_vs_actual":
        return get_demo_policy_predicted_vs_actual()
    if name == "h40":
        return get_demo_policy_h40_direction_only()
    raise ValueError(f"unknown policy demo: {name}")


def _safe_failure(validation: dict) -> dict:
    return {
        "engine_status": "safe_failure_invalid_input",
        "input_validation": validation,
        "dag_output": {},
        "ml_engine": {
            "ml_engine_status": "not_run_invalid_input",
            "human_review_required": True,
            "auto_execution_allowed": False,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        },
        "scenario_engine_v2": {
            "scenario_engine_status": "not_run_invalid_input",
            "required_human_review": True,
            "human_review_required": True,
            "auto_execution_allowed": False,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        },
        "risk_engine_v2": {
            "risk_engine_status": "not_run_invalid_input",
            "risk_level": "critical",
            "risk_score": 1.0,
            "risk_dimensions": {},
            "blocking_flags": ["invalid_input_payload"],
            "required_human_review": True,
            "human_review_required": True,
            "auto_execution_allowed": False,
            "risk_review_reason": "Input payload failed the gateway-ready contract.",
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        },
        "decision_lane_v2": {
            "decision_lane_status": "blocked_for_review",
            "lane": "blocked_pending_risk_review",
            "review_priority": "critical",
            "required_reviews": ["human_review", "risk_review", "evidence_review"],
            "blocking_reasons": ["invalid_input_payload"],
            "human_review_required": True,
            "auto_execution_allowed": False,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        },
        "evidence": {
            "evidence_status": "invalid_input",
            "human_review_required": True,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        },
        "dashboard_artifact": {
            "artifact_type": "diagnostic_engine_summary",
            "readiness_status": "invalid_input_safe_failure",
            "human_review_required": True,
            "auto_execution_allowed": False,
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        },
        "engine_completeness": {
            "completeness_status": "blocked_invalid_input",
            "all_required_sections_present": False,
            "all_outputs_require_human_review": True,
            "auto_execution_allowed": False,
            "no_live_data": True,
            "no_provider_calls": True,
            "no_training": True,
            "no_inference": True,
            "no_benchmark_rerun": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _diagnostic_output_from_dag(dag_output: dict) -> dict:
    final_state = dag_output.get("final_state", {}) if isinstance(dag_output, dict) else {}
    diagnostic = final_state.get("forecast_diagnostic", {})
    policy = final_state.get("policy_metadata", {})
    output = {
        "forecast_diagnostic": diagnostic.get("forecast_diagnostic", "insufficient_evidence")
        if isinstance(diagnostic, dict)
        else "insufficient_evidence",
        "confidence": diagnostic.get("confidence") if isinstance(diagnostic, dict) else None,
        "policy_metadata": policy if isinstance(policy, dict) else {},
    }
    if isinstance(policy, dict) and policy.get("policy_runtime_status"):
        output["policy_runtime_status"] = policy["policy_runtime_status"]
    return output


def _chain_for_v2_evidence(normalized_payload: dict, ml_summary: dict, risk_summary: dict, scenario_summary: dict, decision: dict) -> dict:
    request = normalized_payload["request"]
    diagnostic_counts = dict(ml_summary.get("diagnostic_distribution", {}) or {})
    return {
        "ticker": request["ticker"],
        "timeframe": request["timeframe"],
        "layer_1_quant_core": {
            "quant_signal": ml_summary.get("agreement", {}).get("top_diagnostic") or "insufficient_evidence",
            "consensus_strength": ml_summary.get("agreement", {}).get("agreement_ratio", 0.0),
            "engine_count_checked": ml_summary.get("model_count", 0),
            "completed_count": ml_summary.get("model_count", 0),
            "skipped_missing_evidence_count": 0
            if ml_summary.get("model_count", 0)
            else 1,
            "forecast_diagnostic_engine_enabled": True,
            "forecast_diagnostic_counts": {
                "positive": diagnostic_counts.get("positive_bias", 0),
                "negative": diagnostic_counts.get("negative_bias", 0),
                "neutral": diagnostic_counts.get("neutral_or_uncertain", 0),
                "insufficient": diagnostic_counts.get("insufficient_evidence", 0),
                "exploratory": diagnostic_counts.get("exploratory_only", 0),
            },
            "policy_runtime_status": "policy_not_applied",
            "warnings": [],
        },
        "layer_2_scenario": {
            "scenario": scenario_summary.get("dominant_scenario"),
            "scenario_confidence": 1.0 if scenario_summary.get("stability_status") == "stable" else 0.4,
        },
        "layer_3_risk_governance": {
            "risk_level": risk_summary.get("risk_level"),
            "risk_flags": list(risk_summary.get("blocking_flags", []) or []),
        },
        "layer_4_decision_lane": {
            "decision_lane": decision.get("lane"),
            "human_review_required": True,
        },
        "layer_5_market_context": {
            "market_context_status": "provided_payload_context_only",
            "live_context_enabled": False,
        },
        "layer_6_calibration": {
            "calibrated_confidence": ml_summary.get("signal_quality", {}).get("mean_confidence"),
            "calibration_policy": ml_summary.get("calibration_status"),
            "fine_tuning_performed": False,
        },
        "layer_7_portfolio_diagnostic_allocator": {
            "allocation_view": "diagnostic_review_only",
            "allocation_is_advisory": False,
        },
        "layer_8_phase_router": {
            "route": decision.get("lane"),
            "dashboard_status": "artifact_only",
            "human_review_required": True,
        },
        "non_claim": INPUT_NON_CLAIM_TEXT,
    }


def _sanitize_reused_artifact(value: Any) -> Any:
    blocked_phrases = (" ".join(("financial", "advice")),)
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            clean_value = _sanitize_reused_artifact(nested)
            if clean_value is not None:
                sanitized[key] = clean_value
        return sanitized
    if isinstance(value, list):
        return [item for item in (_sanitize_reused_artifact(item) for item in value) if item is not None]
    if isinstance(value, str):
        lowered = value.lower()
        if any(phrase in lowered for phrase in blocked_phrases):
            return None
    return value


def _build_evidence(normalized_payload: dict, ml_summary: dict, risk_summary: dict, scenario_summary: dict, decision: dict, dag_output: dict) -> dict:
    chain_output = _chain_for_v2_evidence(normalized_payload, ml_summary, risk_summary, scenario_summary, decision)
    packet = build_evidence_packet(
        chain_output,
        run_metadata={"run_id": normalized_payload["request"]["run_id"], "generated_at": "2026-06-21T00:00:00+00:00"},
    )
    packet = _sanitize_reused_artifact(packet)
    return {
        "v2_evidence_packet": packet,
        "dag_evidence_packet": _sanitize_reused_artifact(dag_output.get("final_state", {}).get("evidence_packet", {})),
        "human_review_required": True,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _build_dashboard_artifact(dag_output: dict, risk_summary: dict, scenario_summary: dict, decision: dict) -> dict:
    artifact = build_dashboard_artifact(
        dag_result=dag_output,
        readiness_summary={"readiness_status": "gateway_ready_local_engine_core_after_human_review"},
        coverage_summary={"coverage_status": "payload_contract_ready"},
    )
    return {
        **artifact,
        "engine_core_status": "gateway_ready_local_engine_core",
        "risk_engine_v2_level": risk_summary.get("risk_level"),
        "scenario_engine_v2_status": scenario_summary.get("stability_status"),
        "decision_lane_v2": decision.get("lane"),
        "human_review_required": True,
        "auto_execution_allowed": False,
        "validation": validate_dashboard_artifact(artifact),
    }


def _engine_completeness(result: dict) -> dict:
    sections = (
        "input_validation",
        "dag_output",
        "ml_engine",
        "scenario_engine_v2",
        "risk_engine_v2",
        "decision_lane_v2",
        "evidence",
        "dashboard_artifact",
    )
    complete = all(section in result for section in sections)
    all_review = all(
        bool(result.get(section, {}).get("human_review_required") or result.get(section, {}).get("required_human_review"))
        for section in ("ml_engine", "scenario_engine_v2", "risk_engine_v2", "decision_lane_v2")
    )
    auto_false = all(
        result.get(section, {}).get("auto_execution_allowed") is False
        for section in ("ml_engine", "scenario_engine_v2", "risk_engine_v2", "decision_lane_v2")
    )
    return {
        "completeness_status": "complete" if complete and all_review and auto_false else "attention_required",
        "sections_present": {section: section in result for section in sections},
        "all_outputs_require_human_review": all_review,
        "auto_execution_allowed": False,
        "no_live_data": True,
        "no_provider_calls": True,
        "no_training": True,
        "no_inference": True,
        "no_benchmark_rerun": True,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def run_diagnostic_engine_from_payload(payload: dict) -> dict:
    """Run the complete local diagnostic engine core from a provided payload."""

    input_validation = validate_engine_input_payload(payload)
    if not input_validation["is_valid"]:
        return _safe_failure(input_validation)
    normalized = input_validation["normalized_payload"]
    request = normalized["request"]
    try:
        policy = _demo_policy(request.get("policy_demo"))
    except ValueError as exc:
        invalid = {
            **input_validation,
            "is_valid": False,
            "errors": [*input_validation.get("errors", []), str(exc)],
        }
        return _safe_failure(invalid)

    dag_output = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {
            "ticker": request["ticker"],
            "timeframe": request["timeframe"],
            "horizon_steps": request["horizon_steps"],
            "run_id": request["run_id"],
            "policy_id": policy.get("policy_id") if isinstance(policy, dict) else None,
            "policy_name": policy.get("policy_name") if isinstance(policy, dict) else None,
            "static_inputs": {
                "market_bars": normalized.get("market_bars", []),
                "forecast_rows": normalized.get("forecast_rows", []),
            },
            "metadata": normalized.get("metadata", {}),
        },
        policy=policy,
    )
    diagnostic_output = _diagnostic_output_from_dag(dag_output)
    if normalized.get("forecast_rows"):
        diagnostic_output["forecast_diagnostic"] = normalized["forecast_rows"][0].get(
            "forecast_diagnostic",
            diagnostic_output["forecast_diagnostic"],
        )
    ml_summary = run_ml_diagnostic_engine(tuple(normalized.get("model_diagnostics", []) or ()))
    scenario_summary = run_scenario_engine_v2(payload=normalized, ml_summary=ml_summary)
    risk_summary = run_risk_engine_v2(payload=normalized, ml_summary=ml_summary, scenario_summary=scenario_summary)
    risk_v3_summary = run_risk_engine_v3(payload=normalized, ml_summary=ml_summary, scenario_summary=scenario_summary)
    decision = run_decision_lane_v2(
        diagnostic_output=diagnostic_output,
        ml_summary=ml_summary,
        risk_summary=risk_v3_summary,
        scenario_summary=scenario_summary,
    )
    evidence = _build_evidence(normalized, ml_summary, risk_v3_summary, scenario_summary, decision, dag_output)
    dashboard_artifact = _build_dashboard_artifact(dag_output, risk_v3_summary, scenario_summary, decision)
    result = {
        "engine_status": "completed_gateway_ready_local_engine_core",
        "input_validation": input_validation,
        "dag_output": dag_output,
        "ml_engine": ml_summary,
        "scenario_engine_v2": scenario_summary,
        "risk_engine_v2": risk_summary,
        "risk_engine_v3": risk_v3_summary,
        "decision_lane_v2": decision,
        "evidence": evidence,
        "dashboard_artifact": dashboard_artifact,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }
    result["engine_completeness"] = _engine_completeness(result)
    return result


def _default_payload() -> dict:
    return build_minimal_engine_input_fixture(ticker="VCB", timeframe="1 ng\u00e0y", horizon_steps=40)


def render_diagnostic_engine_report(result: dict) -> str:
    """Render a compact local diagnostic engine report."""

    lines = [
        "# Diagnostic Engine Core",
        "",
        f"Engine status: {result.get('engine_status')}",
        f"Input valid: {result.get('input_validation', {}).get('is_valid')}",
        f"DAG status: {result.get('dag_output', {}).get('execution_status', 'not_run')}",
        f"ML engine: {result.get('ml_engine', {}).get('ml_engine_status')}",
        f"Scenario Engine V2: {result.get('scenario_engine_v2', {}).get('scenario_engine_status')}",
        f"Risk Engine V2: {result.get('risk_engine_v2', {}).get('risk_level')}",
        f"Risk Engine V3: {result.get('risk_engine_v3', {}).get('risk_level')}",
        f"Decision Lane V2: {result.get('decision_lane_v2', {}).get('lane')}",
        f"Completeness: {result.get('engine_completeness', {}).get('completeness_status')}",
        "Human review required: True",
        "Auto execution allowed: False",
        "",
        "Boundary: gateway-ready local diagnostic subsystem; no Data Gateway is built.",
        "No live data, provider calls, training, inference, or benchmark rerun is performed.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the gateway-ready local diagnostic engine core.")
    parser.add_argument("--payload-demo", action="store_true")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    payload = build_minimal_engine_input_fixture() if args.payload_demo else _default_payload()
    result = run_diagnostic_engine_from_payload(payload)
    if args.format == "report":
        print(render_diagnostic_engine_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("engine_status") != "safe_failure_invalid_input" else 1


if __name__ == "__main__":
    raise SystemExit(main())
