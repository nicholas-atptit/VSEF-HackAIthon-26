"""Local text demo surface for the diagnostic engine core."""

from __future__ import annotations

import argparse
import json

from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
from src.hackaithon_mvp.diagnostic_engine_hardening_gate import run_diagnostic_engine_hardening_gate
from src.hackaithon_mvp.engine_input_contract import build_engine_input_contract, build_minimal_engine_input_fixture


CLAIM_BOUNDARY = {
    "local_demo_surface_only": True,
    "writes_files": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "no_web_dashboard": True,
    "human_review_required": True,
    "auto_execution_allowed": False,
}
NON_CLAIM_TEXT = "Local text demo surface only; human review required."


def build_demo_ui_summary() -> dict:
    """Build a compact local demo summary without a web dashboard."""

    contract = build_engine_input_contract()
    payload = build_minimal_engine_input_fixture()
    engine_result = run_diagnostic_engine_from_payload(payload)
    hardening = run_diagnostic_engine_hardening_gate()
    return {
        "demo_ui_status": "ready_for_local_text_demo",
        "sections": [
            "Gateway-ready input contract",
            "ML Diagnostic Engine",
            "Scenario Engine V2",
            "Risk Engine V2",
            "Decision Lane V2",
            "Hardening gate status",
        ],
        "gateway_ready_input_contract": {
            "contract_status": contract.get("contract_status"),
            "required_section_count": len(contract.get("required_sections", []) or []),
        },
        "ml_diagnostic_engine": {
            "status": engine_result.get("ml_engine", {}).get("ml_engine_status"),
            "models": engine_result.get("ml_engine", {}).get("model_count"),
            "agreement": engine_result.get("ml_engine", {}).get("agreement_status"),
        },
        "scenario_engine_v2": {
            "status": engine_result.get("scenario_engine_v2", {}).get("scenario_engine_status"),
            "dominant_scenario": engine_result.get("scenario_engine_v2", {}).get("dominant_scenario"),
            "stability": engine_result.get("scenario_engine_v2", {}).get("stability_status"),
        },
        "risk_engine_v2": {
            "status": engine_result.get("risk_engine_v2", {}).get("risk_engine_status"),
            "risk_level": engine_result.get("risk_engine_v2", {}).get("risk_level"),
        },
        "decision_lane_v2": {
            "status": engine_result.get("decision_lane_v2", {}).get("decision_lane_status"),
            "lane": engine_result.get("decision_lane_v2", {}).get("lane"),
            "auto_execution_allowed": False,
        },
        "hardening_gate_status": hardening.get("hardening_status"),
        "human_review_required": True,
        "auto_execution_allowed": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_demo_ui_text(summary: dict) -> str:
    """Render the local demo summary as plain text."""

    lines = [
        "# Diagnostic Engine Demo",
        "",
        f"Demo UI status: {summary.get('demo_ui_status')}",
        "",
        "## Gateway-ready input contract",
        f"Contract status: {summary.get('gateway_ready_input_contract', {}).get('contract_status')}",
        f"Required sections: {summary.get('gateway_ready_input_contract', {}).get('required_section_count')}",
        "",
        "## ML Diagnostic Engine",
        f"Status: {summary.get('ml_diagnostic_engine', {}).get('status')}",
        f"Models: {summary.get('ml_diagnostic_engine', {}).get('models')}",
        f"Agreement: {summary.get('ml_diagnostic_engine', {}).get('agreement')}",
        "",
        "## Scenario Engine V2",
        f"Status: {summary.get('scenario_engine_v2', {}).get('status')}",
        f"Dominant scenario: {summary.get('scenario_engine_v2', {}).get('dominant_scenario')}",
        f"Stability: {summary.get('scenario_engine_v2', {}).get('stability')}",
        "",
        "## Risk Engine V2",
        f"Status: {summary.get('risk_engine_v2', {}).get('status')}",
        f"Risk level: {summary.get('risk_engine_v2', {}).get('risk_level')}",
        "",
        "## Decision Lane V2",
        f"Status: {summary.get('decision_lane_v2', {}).get('status')}",
        f"Lane: {summary.get('decision_lane_v2', {}).get('lane')}",
        "Auto execution allowed: False",
        "",
        "## Hardening gate status",
        f"Status: {summary.get('hardening_gate_status')}",
        "",
        "## Boundary",
        "Local text demo only; no web dashboard is built.",
        "No live data, provider calls, training, inference, or benchmark rerun is performed.",
        "Human review remains required.",
        str(summary.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render the local diagnostic engine demo surface.")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    summary = build_demo_ui_summary()
    if args.format == "text":
        print(render_demo_ui_text(summary), end="")
    else:
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
