"""Local scheduler-like diagnostic runner contract."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.quant_core_policy_registry import get_demo_policy_h40_direction_only


DEFAULT_TIMEFRAME = "1 ng\u00e0y"
NON_CLAIM_TEXT = "Local dry-run diagnostic runner contract; human review remains required."
CLAIM_BOUNDARY = {
    "local_runner_contract_only": True,
    "background_process": False,
    "writes_files_by_default": False,
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


def build_periodic_runner_plan(
    *,
    interval_seconds: int = 60,
    max_iterations: int = 1,
) -> dict:
    """Build a bounded local runner plan."""

    interval_seconds = int(interval_seconds)
    max_iterations = int(max_iterations)
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    return {
        "plan_status": "ready",
        "interval_seconds": interval_seconds,
        "max_iterations": max_iterations,
        "dry_run_default": True,
        "infinite_loop_default": False,
        "background_process": False,
        "writes_files_by_default": False,
        "uses_dag_execution": True,
        "sleep_performed_by_default": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _compact_once_result(dag_result: dict[str, Any], *, policy_demo: str | None) -> dict[str, Any]:
    final_state = dag_result.get("final_state", {})
    chain_output = final_state.get("chain_output", {})
    policy_metadata = final_state.get("policy_metadata", {})
    quant_core_output = final_state.get("quant_core_output", {})
    return {
        "runner_status": "completed" if dag_result.get("execution_status") != "failed" else "failed",
        "runner_mode": "single_iteration",
        "ticker": final_state.get("ticker"),
        "timeframe": final_state.get("timeframe"),
        "horizon_steps": final_state.get("horizon_steps"),
        "dag_execution_status": dag_result.get("execution_status"),
        "forecast_diagnostic": final_state.get("forecast_diagnostic", {}).get("forecast_diagnostic"),
        "route": chain_output.get("layer_8_phase_router", {}).get("route"),
        "risk_level": chain_output.get("layer_3_risk_governance", {}).get("risk_level"),
        "policy_demo": policy_demo,
        "policy_runtime_status": (
            policy_metadata.get("policy_runtime_status")
            or quant_core_output.get("policy_runtime_status")
            or "policy_not_applied"
        ),
        "node_count": len(dag_result.get("node_results", []) or []),
        "writes_performed": False,
        "live_data_used": False,
        "provider_calls_used": False,
        "training_used": False,
        "inference_used": False,
        "benchmark_rerun": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def run_periodic_diagnostic_once(
    *,
    ticker: str = "DEMO",
    timeframe: str = DEFAULT_TIMEFRAME,
    horizon_steps: int = 1,
    policy_demo: str | None = None,
) -> dict:
    """Run one local DAG diagnostic iteration."""

    policy = _demo_policy(policy_demo)
    dag_result = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {
            "ticker": ticker,
            "timeframe": timeframe,
            "horizon_steps": horizon_steps,
            "policy_id": policy.get("policy_id") if isinstance(policy, dict) else None,
            "policy_name": policy.get("policy_name") if isinstance(policy, dict) else None,
        },
        policy=policy,
    )
    return _compact_once_result(dag_result, policy_demo=policy_demo)


def run_periodic_diagnostic_loop(
    *,
    interval_seconds: int = 60,
    max_iterations: int = 1,
    dry_run: bool = True,
) -> dict:
    """Run a bounded local diagnostic loop without sleeping or background work."""

    plan = build_periodic_runner_plan(interval_seconds=interval_seconds, max_iterations=max_iterations)
    iterations = [run_periodic_diagnostic_once() for _ in range(plan["max_iterations"])]
    failed = any(item.get("runner_status") == "failed" for item in iterations)
    return {
        "loop_status": "failed" if failed else "completed",
        "dry_run": bool(dry_run),
        "interval_seconds": plan["interval_seconds"],
        "max_iterations": plan["max_iterations"],
        "iteration_count": len(iterations),
        "iterations": iterations,
        "writes_performed": False,
        "background_process": False,
        "sleep_performed": False,
        "live_data_used": False,
        "provider_calls_used": False,
        "training_used": False,
        "inference_used": False,
        "benchmark_rerun": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a bounded local diagnostic runner contract.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--ticker", default="DEMO")
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    parser.add_argument("--horizon-steps", type=int, default=1)
    parser.add_argument("--policy-demo", choices=("h40",), default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        if args.plan:
            output = build_periodic_runner_plan(
                interval_seconds=args.interval_seconds,
                max_iterations=args.max_iterations,
            )
        elif args.once:
            output = run_periodic_diagnostic_once(
                ticker=args.ticker,
                timeframe=args.timeframe,
                horizon_steps=args.horizon_steps,
                policy_demo=args.policy_demo,
            )
        else:
            output = run_periodic_diagnostic_loop(
                interval_seconds=args.interval_seconds,
                max_iterations=args.max_iterations,
                dry_run=args.dry_run,
            )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0 if output.get("runner_status", output.get("loop_status", output.get("plan_status"))) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
