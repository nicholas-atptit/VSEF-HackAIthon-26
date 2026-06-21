"""Dashboard artifact export contract without a web dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag


DEFAULT_TIMEFRAME = "1 ng\u00e0y"
NON_CLAIM_TEXT = "Dashboard artifact export only; no web dashboard is built."
CLAIM_BOUNDARY = {
    "artifact_export_only": True,
    "dashboard_web_app_created": False,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
}
REQUIRED_FIELDS = (
    "artifact_type",
    "generated_from",
    "dag_status",
    "forecast_diagnostic",
    "route",
    "risk_level",
    "policy_status",
    "readiness_status",
    "claim_boundary",
    "non_claim",
)


def _default_dag_result() -> dict:
    return execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {"ticker": "VCB", "timeframe": DEFAULT_TIMEFRAME, "horizon_steps": 1},
    )


def build_dashboard_artifact(
    *,
    dag_result: dict | None = None,
    readiness_summary: dict | None = None,
    coverage_summary: dict | None = None,
) -> dict:
    """Build a compact dashboard-facing JSON object for future display."""

    dag_result = dag_result or _default_dag_result()
    final_state = dag_result.get("final_state", {})
    chain_output = final_state.get("chain_output", {})
    policy_metadata = final_state.get("policy_metadata", {})
    quant_core_output = final_state.get("quant_core_output", {})
    return {
        "artifact_type": "dashboard_ready_summary",
        "generated_from": "local_static_demo",
        "dag_status": dag_result.get("execution_status"),
        "forecast_diagnostic": final_state.get("forecast_diagnostic", {}).get("forecast_diagnostic"),
        "route": chain_output.get("layer_8_phase_router", {}).get("route"),
        "risk_level": chain_output.get("layer_3_risk_governance", {}).get("risk_level"),
        "policy_status": (
            policy_metadata.get("policy_runtime_status")
            or quant_core_output.get("policy_runtime_status")
            or "policy_not_applied"
        ),
        "readiness_status": (
            (readiness_summary or {}).get("readiness_status")
            or (readiness_summary or {}).get("alignment_status")
            or "local_static_artifact_only"
        ),
        "coverage_status": (coverage_summary or {}).get("coverage_status"),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_dashboard_artifact_json(artifact: dict) -> str:
    """Render the dashboard artifact as stable JSON."""

    return json.dumps(artifact, indent=2, sort_keys=True, default=str) + "\n"


def validate_dashboard_artifact(artifact: dict) -> dict:
    """Validate the compact dashboard artifact contract."""

    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in artifact:
            errors.append(f"missing field: {field}")
    if artifact.get("artifact_type") != "dashboard_ready_summary":
        errors.append("artifact_type must be dashboard_ready_summary")
    if artifact.get("generated_from") != "local_static_demo":
        errors.append("generated_from must be local_static_demo")
    boundary = artifact.get("claim_boundary", {})
    for key, expected in CLAIM_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"claim_boundary.{key} must be {expected}")
    if artifact.get("coverage_status") is None:
        warnings.append("coverage_status not provided")
    return {"is_valid": not errors, "errors": errors, "warnings": warnings}


def _render_report(artifact: dict) -> str:
    validation = validate_dashboard_artifact(artifact)
    lines = [
        "# Dashboard Artifact Export",
        "",
        f"Artifact type: {artifact.get('artifact_type')}",
        f"Generated from: {artifact.get('generated_from')}",
        f"DAG status: {artifact.get('dag_status')}",
        f"Forecast diagnostic: {artifact.get('forecast_diagnostic')}",
        f"Route: {artifact.get('route')}",
        f"Risk level: {artifact.get('risk_level')}",
        f"Policy status: {artifact.get('policy_status')}",
        f"Valid artifact: {validation.get('is_valid')}",
        "",
        "Boundary: compact JSON artifact only; no web dashboard is built.",
        NON_CLAIM_TEXT,
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a compact dashboard artifact object.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    parser.add_argument("--write", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    artifact = build_dashboard_artifact()
    validation = validate_dashboard_artifact(artifact)
    if args.write:
        output_path = Path(args.write)
        output_path.write_text(render_dashboard_artifact_json(artifact), encoding="utf-8")
        artifact = {**artifact, "write_result": {"written": True, "path": str(output_path)}}
    if args.format == "report":
        print(_render_report(artifact), end="")
    else:
        print(render_dashboard_artifact_json(artifact), end="")
    return 0 if validation.get("is_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
