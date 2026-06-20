"""Deterministic local end-to-end demo for the MVP diagnostic flow."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.diagnostic_dag.dag_executor import execute_diagnostic_dag
from src.hackaithon_mvp.diagnostic_dag.dag_registry import build_default_diagnostic_dag
from src.hackaithon_mvp.forecast_actual_dag_loop import run_forecast_actual_loop
from src.hackaithon_mvp.quant_core_policy_registry import (
    get_demo_policy_h40_direction_only,
    get_demo_policy_predicted_vs_actual,
)


DEMO_TICKER = "DEMO"
DEMO_TIMEFRAME = "1d"
DEMO_TIMEFRAME_INPUT = "1 ngày"
DEMO_HORIZON_STEPS = 1
CLAIM_BOUNDARY = {
    "local_demo_fixture_only": True,
    "storage_write_default": False,
    "server_database_created": False,
    "data_gateway_created": False,
    "live_data_enabled": False,
    "provider_calls_enabled": False,
    "training_enabled": False,
    "inference_enabled": False,
    "benchmark_rerun": False,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Local deterministic diagnostic demo only; no external data or operational decision."


def _demo_policy(name: str | None) -> dict | None:
    if name is None:
        return None
    if name == "predicted_vs_actual":
        return get_demo_policy_predicted_vs_actual()
    if name == "h40":
        return get_demo_policy_h40_direction_only()
    raise ValueError(f"unknown policy demo: {name}")


def build_demo_forecast_rows() -> tuple[dict, ...]:
    """Build a tiny deterministic forecast row fixture."""

    return (
        {
            "ticker": DEMO_TICKER,
            "timeframe": DEMO_TIMEFRAME,
            "prediction_timestamp": "2026-01-01T00:00:00+07:00",
            "horizon_steps": DEMO_HORIZON_STEPS,
            "forecast_diagnostic": "positive_bias",
            "engine_id": "demo.local.static.h1",
            "model_key": "demo_static_baseline",
            "model_family": "classification",
            "diagnostic_score": 0.9,
            "confidence": 0.9,
            "route": "human_review",
            "risk_level": "bounded_demo",
            "source": "end_to_end_demo_fixture",
        },
    )


def build_demo_bar_rows() -> tuple[dict, ...]:
    """Build tiny deterministic local OHLCV bar rows."""

    return (
        {
            "ticker": DEMO_TICKER,
            "timeframe": DEMO_TIMEFRAME,
            "timestamp": "2026-01-01T00:00:00+07:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1000,
            "source": "end_to_end_demo_fixture",
        },
        {
            "ticker": DEMO_TICKER,
            "timeframe": DEMO_TIMEFRAME,
            "timestamp": "2026-01-02T00:00:00+07:00",
            "open": 102.0,
            "high": 103.0,
            "low": 101.0,
            "close": 102.0,
            "volume": 1100,
            "source": "end_to_end_demo_fixture",
        },
    )


def _compact_policy(policy: dict | None) -> dict[str, Any]:
    if not isinstance(policy, dict):
        return {"policy_runtime_status": "policy_not_applied"}
    metrics = policy.get("validation_metrics", {})
    return {
        "policy_id": policy.get("policy_id"),
        "policy_name": policy.get("policy_name"),
        "policy_validation_accuracy": metrics.get("validation_accuracy") if isinstance(metrics, dict) else None,
        "policy_validation_balanced_accuracy": (
            metrics.get("validation_balanced_accuracy") if isinstance(metrics, dict) else None
        ),
        "policy_validation_coverage": metrics.get("validation_coverage") if isinstance(metrics, dict) else None,
    }


def run_end_to_end_demo(
    *,
    persist: bool = False,
    storage_root: str | None = None,
    policy_demo: str | None = None,
    match_mode: str = "exact",
) -> dict:
    """Run the deterministic local MVP demo end to end."""

    if persist and not storage_root:
        raise ValueError("storage_root is required when persist is true")
    policy = _demo_policy(policy_demo)
    dag_result = execute_diagnostic_dag(
        build_default_diagnostic_dag(),
        {
            "ticker": DEMO_TICKER,
            "timeframe": DEMO_TIMEFRAME_INPUT,
            "horizon_steps": DEMO_HORIZON_STEPS,
            "policy_id": policy.get("policy_id") if isinstance(policy, dict) else None,
            "policy_name": policy.get("policy_name") if isinstance(policy, dict) else None,
        },
        policy=policy,
    )
    forecast_rows = build_demo_forecast_rows()
    bar_rows = build_demo_bar_rows()
    loop_result = run_forecast_actual_loop(
        forecast_rows=forecast_rows,
        bar_rows=bar_rows,
        storage_root=storage_root,
        ticker=DEMO_TICKER,
        timeframe=DEMO_TIMEFRAME,
        date="2026-01-01",
        match_mode=match_mode,
        top_k=1,
        persist=persist,
    )
    evaluation = loop_result.get("evaluation", {})
    storage_summary = loop_result.get("storage_write_summary", {})
    summary = {
        "demo_status": "completed"
        if dag_result.get("execution_status") != "failed" and loop_result.get("loop_status") == "completed"
        else "failed",
        "dag_execution_status": dag_result.get("execution_status"),
        "dag_run_id": dag_result.get("run_id"),
        "dag_node_count": len(dag_result.get("node_results", []) or []),
        "forecast_rows_total": len(forecast_rows),
        "bar_rows_total": len(bar_rows),
        "actual_outcome_rows": loop_result.get("actual_outcome_rows", 0),
        "evaluation_status": loop_result.get("evaluation_status"),
        "directional_accuracy": evaluation.get("directional_accuracy"),
        "balanced_directional_accuracy": evaluation.get("balanced_directional_accuracy"),
        "coverage_ratio": evaluation.get("coverage_ratio"),
        "storage_write_enabled": bool(loop_result.get("storage_write_enabled")),
        "records_written": int(storage_summary.get("records_written", 0) or 0),
        "storage_format": storage_summary.get("storage_format"),
        "policy_demo": policy_demo,
        "policy_metadata": _compact_policy(policy),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }
    if persist:
        summary["storage_root"] = str(storage_root).replace("\\", "/")
    return summary


def _format_value(value: Any) -> str:
    return "unavailable" if value is None else str(value)


def render_end_to_end_demo_report(summary: dict) -> str:
    """Render a compact neutral report for the local demo summary."""

    lines = [
        "# End-to-End Local Demo",
        "",
        "## Scope",
        "Local-only diagnostic fixture using tiny deterministic rows.",
        "Human review is required.",
        "No operational decision is produced.",
        "",
        "## Run Summary",
        f"Demo status: {summary.get('demo_status')}",
        f"DAG status: {summary.get('dag_execution_status')}",
        f"Forecast rows: {summary.get('forecast_rows_total')}",
        f"Bar rows: {summary.get('bar_rows_total')}",
        f"Actual outcome rows: {summary.get('actual_outcome_rows')}",
        f"Evaluation status: {summary.get('evaluation_status')}",
        "",
        "## Evaluation",
        f"Directional accuracy: {_format_value(summary.get('directional_accuracy'))}",
        f"Coverage ratio: {_format_value(summary.get('coverage_ratio'))}",
        "",
        "## Storage",
        f"Storage write enabled: {summary.get('storage_write_enabled')}",
        f"Records written: {summary.get('records_written')}",
        "",
        "## Boundary",
        "No live data, provider calls, model training, model inference, or benchmark rerun is performed.",
        "Persistence is disabled unless explicitly requested.",
        str(summary.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local end-to-end MVP demo.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--storage-root", default=None)
    parser.add_argument("--policy-demo", choices=("predicted_vs_actual", "h40"), default=None)
    parser.add_argument("--match-mode", choices=("exact", "nearest_prior"), default="exact")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.persist and not args.storage_root:
        parser.error("--persist requires --storage-root")
    try:
        summary = run_end_to_end_demo(
            persist=bool(args.persist),
            storage_root=args.storage_root,
            policy_demo=args.policy_demo,
            match_mode=args.match_mode,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.format == "report":
        print(render_end_to_end_demo_report(summary), end="")
    else:
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary.get("demo_status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
