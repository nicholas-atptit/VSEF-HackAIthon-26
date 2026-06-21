"""Local DAG forecast output verification for diagram demo narration."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.quant_core_policy_registry import get_demo_policy_h40_direction_only


DEMO_TIMEFRAME = "1 ng\u00e0y"
NON_CLAIM_TEXT = "Research diagnostic verification only; human review remains required."
CLAIM_BOUNDARY = {
    "local_static_only": True,
    "writes_files": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
}


def _demo_policy(policy_demo: str | None) -> dict | None:
    if policy_demo is None:
        return None
    if policy_demo == "h40":
        return get_demo_policy_h40_direction_only()
    raise ValueError(f"unknown policy demo: {policy_demo}")


def build_dag_forecast_verification_cases() -> tuple[dict, ...]:
    """Build the fixed local DAG verification cases used by the diagram demo."""

    return (
        {
            "case_id": "demo_no_policy",
            "ticker": "DEMO",
            "timeframe": DEMO_TIMEFRAME,
            "horizon_steps": 1,
            "policy_demo": None,
        },
        {
            "case_id": "demo_h40_policy",
            "ticker": "DEMO",
            "timeframe": DEMO_TIMEFRAME,
            "horizon_steps": 1,
            "policy_demo": "h40",
        },
        {
            "case_id": "vcb_no_policy",
            "ticker": "VCB",
            "timeframe": DEMO_TIMEFRAME,
            "horizon_steps": 1,
            "policy_demo": None,
        },
        {
            "case_id": "vcb_h40_policy",
            "ticker": "VCB",
            "timeframe": DEMO_TIMEFRAME,
            "horizon_steps": 1,
            "policy_demo": "h40",
        },
    )


def _warning_count(dag_result: dict[str, Any]) -> int:
    return sum(len(node.get("warnings", []) or []) for node in dag_result.get("node_results", []) or [])


def _is_static_local_only(dag_result: dict[str, Any]) -> bool:
    boundary = dag_result.get("claim_boundary", {})
    return (
        boundary.get("no_live_data") is True
        and boundary.get("no_provider_calls") is True
        and boundary.get("no_training") is True
        and boundary.get("no_inference") is True
        and boundary.get("human_review_required") is True
    )


def _verification_row(case: dict[str, Any], dag_result: dict[str, Any], policy: dict | None) -> dict[str, Any]:
    final_state = dag_result.get("final_state", {})
    chain_output = final_state.get("chain_output", {})
    forecast_payload = final_state.get("forecast_diagnostic", {})
    policy_metadata = final_state.get("policy_metadata", {})
    quant_core_output = final_state.get("quant_core_output", {})
    route = chain_output.get("layer_8_phase_router", {}).get("route")
    risk_level = chain_output.get("layer_3_risk_governance", {}).get("risk_level")
    policy_runtime_status = (
        policy_metadata.get("policy_runtime_status")
        or quant_core_output.get("policy_runtime_status")
        or "policy_not_applied"
    )
    return {
        "case_id": case["case_id"],
        "ticker": final_state.get("ticker", case["ticker"]),
        "timeframe": final_state.get("timeframe", case["timeframe"]),
        "horizon_steps": final_state.get("horizon_steps", case["horizon_steps"]),
        "execution_status": dag_result.get("execution_status"),
        "forecast_diagnostic": forecast_payload.get("forecast_diagnostic"),
        "pre_policy_forecast_diagnostic": policy_metadata.get("pre_policy_forecast_diagnostic"),
        "route": route,
        "risk_level": risk_level,
        "policy_runtime_status": policy_runtime_status,
        "policy_id": policy_metadata.get("policy_id") or (policy.get("policy_id") if policy else None),
        "policy_name": policy_metadata.get("policy_name") or (policy.get("policy_name") if policy else None),
        "evidence_packet_present": bool(final_state.get("evidence_packet")),
        "diagnostic_report_present": bool(final_state.get("diagnostic_report")),
        "node_count": len(dag_result.get("node_results", []) or []),
        "warning_count": _warning_count(dag_result),
        "is_static_local_only": _is_static_local_only(dag_result),
    }


def run_dag_forecast_verification_cases() -> dict:
    """Execute the fixed local DAG cases and return compact verification rows."""

    nodes = build_default_diagnostic_dag()
    rows: list[dict[str, Any]] = []
    for case in build_dag_forecast_verification_cases():
        policy = _demo_policy(case.get("policy_demo"))
        context = {
            "ticker": case["ticker"],
            "timeframe": case["timeframe"],
            "horizon_steps": case["horizon_steps"],
            "policy_id": policy.get("policy_id") if isinstance(policy, dict) else None,
            "policy_name": policy.get("policy_name") if isinstance(policy, dict) else None,
        }
        dag_result = execute_diagnostic_dag(nodes, context, policy=policy)
        rows.append(_verification_row(case, dag_result, policy))

    completed_count = sum(1 for row in rows if str(row.get("execution_status", "")).startswith("completed"))
    preserved_count = sum(
        1
        for row in rows
        if row.get("policy_runtime_status") == "non_directional_preserved"
        and row.get("forecast_diagnostic") == row.get("pre_policy_forecast_diagnostic")
    )
    return {
        "verification_status": "completed" if completed_count == len(rows) else "attention_required",
        "case_count": len(rows),
        "completed_case_count": completed_count,
        "static_local_only_case_count": sum(1 for row in rows if row.get("is_static_local_only") is True),
        "non_directional_preserved_count": preserved_count,
        "warning_count": sum(int(row.get("warning_count", 0) or 0) for row in rows),
        "cases": rows,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_dag_forecast_verification_table(result: dict) -> str:
    """Render the verification result as a compact text table."""

    rows = result.get("cases", []) or []
    lines = [
        "# DAG Forecast Output Verification",
        "",
        f"Verification status: {result.get('verification_status')}",
        f"Case count: {result.get('case_count')}",
        "",
        (
            "case_id | ticker | policy | status | forecast_diagnostic | "
            "pre_policy_forecast_diagnostic | route | risk_level | policy_runtime_status | nodes | warnings"
        ),
        "--- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---",
    ]
    for row in rows:
        policy = "h40" if row.get("policy_id") else "none"
        lines.append(
            " | ".join(
                str(value)
                for value in (
                    row.get("case_id"),
                    row.get("ticker"),
                    policy,
                    row.get("execution_status"),
                    row.get("forecast_diagnostic"),
                    row.get("pre_policy_forecast_diagnostic") or "none",
                    row.get("route"),
                    row.get("risk_level"),
                    row.get("policy_runtime_status"),
                    row.get("node_count"),
                    row.get("warning_count"),
                )
            )
        )
    lines.extend(
        [
            "",
            "Boundary: local/static verification only; no files are written.",
            "Human review remains required.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local DAG forecast output verification cases.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_dag_forecast_verification_cases()
    if args.format == "report":
        print(render_dag_forecast_verification_table(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("verification_status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
