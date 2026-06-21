"""Local/static diagnostic DAG backtest harness."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual
from src.hackaithon_mvp.offline_data_gateway import build_payload_from_local_records, normalize_market_bar_records


CLAIM_BOUNDARY = {
    "local_static_harness_only": True,
    "diagnostic_test_only": True,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "writes_files": False,
    "human_review_required": True,
    "auto_execution_allowed": False,
}
NON_CLAIM_TEXT = "Local deterministic diagnostic checks only; not an execution backtest or performance claim."


def build_dag_backtest_fixture() -> dict:
    """Build a tiny deterministic local fixture for harness checks."""

    bars = (
        {"ticker": "DEMO", "timestamp": "2026-01-01", "open": 100, "high": 105, "low": 99, "close": 102, "volume": 100000},
        {"ticker": "DEMO", "timestamp": "2026-01-02", "open": 102, "high": 106, "low": 101, "close": 104, "volume": 120000},
        {"ticker": "DEMO", "timestamp": "2026-01-03", "open": 104, "high": 107, "low": 103, "close": 106, "volume": 130000},
        {"ticker": "DEMO", "timestamp": "2026-01-04", "open": 106, "high": 108, "low": 105, "close": 107, "volume": 110000},
    )
    payload = build_payload_from_local_records(records=bars, ticker="DEMO", timeframe="1 ngày", horizon_steps=1)
    return {
        "fixture_status": "ready",
        "bars": bars,
        "payloads": (payload,),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _diagnostic_label(engine_result: dict[str, Any]) -> str:
    if engine_result.get("ml_engine", {}).get("agreement", {}).get("top_diagnostic"):
        return str(engine_result["ml_engine"]["agreement"]["top_diagnostic"])
    final_state = engine_result.get("dag_output", {}).get("final_state", {})
    diagnostic = final_state.get("forecast_diagnostic", {}) if isinstance(final_state, dict) else {}
    if isinstance(diagnostic, dict):
        return str(diagnostic.get("forecast_diagnostic") or "insufficient_evidence")
    return "insufficient_evidence"


def _risk_summary(engine_result: dict[str, Any]) -> dict:
    return engine_result.get("risk_engine_v3") or engine_result.get("risk_engine_v2") or {}


def run_dag_backtest_from_payloads(
    *,
    payloads: tuple[dict, ...],
) -> dict:
    """Run Diagnostic Engine repeatedly over local payload windows."""

    errors: list[str] = []
    engine_results: list[dict[str, Any]] = []
    for index, payload in enumerate(payloads):
        if not isinstance(payload, dict):
            errors.append(f"payloads[{index}] must be an object")
            continue
        engine_results.append(run_diagnostic_engine_from_payload(payload))

    run_count = len(engine_results)
    completed_count = sum(1 for result in engine_results if str(result.get("engine_status", "")).startswith("completed"))
    diagnostic_distribution = Counter(_diagnostic_label(result) for result in engine_results)
    route_distribution = Counter(str(result.get("decision_lane_v2", {}).get("lane", "missing")) for result in engine_results)
    risk_distribution = Counter(str(_risk_summary(result).get("risk_level", "missing")) for result in engine_results)
    decision_lane_distribution = Counter(str(result.get("decision_lane_v2", {}).get("lane", "missing")) for result in engine_results)
    warning_count = sum(len(result.get("input_validation", {}).get("warnings", []) or []) for result in engine_results)
    insufficient_count = diagnostic_distribution.get("insufficient_evidence", 0) + decision_lane_distribution.get("blocked_pending_evidence", 0)
    neutral_count = diagnostic_distribution.get("neutral_or_uncertain", 0)
    critical_risk_count = risk_distribution.get("critical", 0)
    human_review_count = sum(1 for result in engine_results if result.get("decision_lane_v2", {}).get("human_review_required") is True)
    auto_execution_count = sum(1 for result in engine_results if result.get("decision_lane_v2", {}).get("auto_execution_allowed") is True)
    forecast_actual_rows = []
    for payload in payloads:
        for row in payload.get("forecast_rows", []) if isinstance(payload, dict) else []:
            if "actual_future_return" in row and "actual_direction_label" in row:
                forecast_actual_rows.append(row)
    evaluation_summary = evaluate_forecast_vs_actual(tuple(forecast_actual_rows)) if forecast_actual_rows else None
    return {
        "backtest_status": "completed" if not errors else "completed_with_errors",
        "payload_count": len(payloads),
        "engine_run_count": run_count,
        "completed_count": completed_count,
        "engine_completion_rate": round(completed_count / run_count, 6) if run_count else 0.0,
        "warning_count": warning_count,
        "insufficient_evidence_count": insufficient_count,
        "neutral_count": neutral_count,
        "critical_risk_count": critical_risk_count,
        "human_review_count": human_review_count,
        "auto_execution_count": auto_execution_count,
        "diagnostic_distribution": dict(sorted(diagnostic_distribution.items())),
        "route_distribution": dict(sorted(route_distribution.items())),
        "risk_distribution": dict(sorted(risk_distribution.items())),
        "decision_lane_distribution": dict(sorted(decision_lane_distribution.items())),
        "evaluation_summary": evaluation_summary,
        "errors": errors,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def run_dag_backtest_from_local_bars(
    *,
    bars: tuple[dict, ...],
    ticker: str,
    timeframe: str = "1 ngày",
    horizon_steps: int = 1,
) -> dict:
    """Create rolling local payload windows from bars and run the harness."""

    normalized_bars = normalize_market_bar_records(bars)
    payloads: list[dict[str, Any]] = []
    for end_index in range(2, len(normalized_bars) + 1):
        payloads.append(
            build_payload_from_local_records(
                records=tuple(normalized_bars[:end_index]),
                ticker=ticker,
                timeframe=timeframe,
                horizon_steps=horizon_steps,
            )
        )
    if not payloads and normalized_bars:
        payloads.append(
            build_payload_from_local_records(
                records=normalized_bars,
                ticker=ticker,
                timeframe=timeframe,
                horizon_steps=horizon_steps,
            )
        )
    return run_dag_backtest_from_payloads(payloads=tuple(payloads))


def render_dag_backtest_report(result: dict) -> str:
    """Render a compact local harness report."""

    lines = [
        "# DAG Backtest Harness",
        "",
        f"Backtest status: {result.get('backtest_status')}",
        f"Payload count: {result.get('payload_count')}",
        f"Engine runs: {result.get('engine_run_count')}",
        f"Completion rate: {result.get('engine_completion_rate')}",
        f"Warnings: {result.get('warning_count')}",
        f"Insufficient evidence count: {result.get('insufficient_evidence_count')}",
        f"Neutral count: {result.get('neutral_count')}",
        f"Critical risk count: {result.get('critical_risk_count')}",
        f"Human review count: {result.get('human_review_count')}",
        f"Auto execution count: {result.get('auto_execution_count')}",
        "",
        f"Diagnostic distribution: {json.dumps(result.get('diagnostic_distribution', {}), sort_keys=True)}",
        f"Risk distribution: {json.dumps(result.get('risk_distribution', {}), sort_keys=True)}",
        f"Decision lane distribution: {json.dumps(result.get('decision_lane_distribution', {}), sort_keys=True)}",
        "",
        "## Boundary",
        "Local/static diagnostic harness only; not an execution backtest and not a benchmark rerun.",
        "No live data, provider calls, training, or inference is performed.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local/static diagnostic DAG harness.")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    fixture = build_dag_backtest_fixture()
    result = run_dag_backtest_from_payloads(payloads=tuple(fixture["payloads"]))
    if args.format == "report":
        print(render_dag_backtest_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("backtest_status", "").startswith("completed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
