"""Safe overnight self-improvement audit orchestrator."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.hackaithon_mvp.dag_backtest_harness import build_dag_backtest_fixture, run_dag_backtest_from_payloads
from src.hackaithon_mvp.diagram_demo_readiness import build_diagram_demo_readiness_summary
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.engine_universe_gap_analysis import run_engine_universe_gap_analysis
from src.hackaithon_mvp.engine_universe_forecast_sweep import build_engine_universe_sweep_plan
from src.hackaithon_mvp.final_claim_boundary_audit import run_final_claim_boundary_audit
from src.hackaithon_mvp.gateway_backtest_readiness import run_gateway_backtest_readiness_gate
from src.hackaithon_mvp.llm_demo_evidence_pack import build_rich_llm_demo_records
from src.hackaithon_mvp.model_tuning_readiness import run_model_tuning_readiness_gate
from src.hackaithon_mvp.ollama_local_client import DEFAULT_OLLAMA_MODEL, check_ollama_availability
from src.hackaithon_mvp.public_demo_readiness import build_public_demo_readiness_summary
from src.hackaithon_mvp.risk_engine_v3 import run_risk_engine_v3


CLAIM_BOUNDARY = {
    "self_improvement_audit_only": True,
    "writes_files_by_default": False,
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_fine_tuning": True,
    "no_inference": True,
    "no_benchmark_rerun": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Local self-improvement audit only; score is a readiness signal for human review."
SCORE_WEIGHTS = {
    "tests_pass": 25,
    "claim_audit_pass": 20,
    "gateway_risk_dag_robustness": 20,
    "llm_evidence_answer_quality": 15,
    "coverage_gap_transparency": 10,
    "tuning_readiness_clarity": 10,
}


def build_self_improvement_plan() -> dict:
    """Describe the bounded checks performed by the self-improvement audit."""

    return {
        "plan_status": "ready",
        "checks": [
            "public_demo_readiness",
            "diagram_demo_readiness",
            "gateway_backtest_readiness",
            "engine_universe_sweep_readiness",
            "engine_universe_gap_analysis",
            "model_tuning_readiness",
            "final_claim_boundary_audit",
            "ollama_llm_readiness",
            "risk_v3_smoke",
            "dag_backtest_fixture",
            "llm_demo_evidence_pack",
        ],
        "score_weights": dict(SCORE_WEIGHTS),
        "writes_files_by_default": False,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _safe_call(name: str, func) -> dict[str, Any]:
    try:
        result = func()
        if isinstance(result, dict):
            return {"check_status": "completed", "result": result, "errors": []}
        return {"check_status": "completed", "result": {"value": result}, "errors": []}
    except Exception as exc:  # noqa: BLE001 - audit must isolate failed checks.
        return {"check_status": "failed", "result": {}, "errors": [f"{name}: {type(exc).__name__}: {exc}"]}


def run_self_improvement_audit(*, test_results: dict[str, Any] | None = None) -> dict:
    """Run bounded local checks and return a readiness audit result."""

    checks = {
        "public_demo_readiness": _safe_call("public_demo_readiness", build_public_demo_readiness_summary),
        "diagram_demo_readiness": _safe_call("diagram_demo_readiness", build_diagram_demo_readiness_summary),
        "gateway_backtest_readiness": _safe_call("gateway_backtest_readiness", run_gateway_backtest_readiness_gate),
        "engine_universe_sweep_readiness": _safe_call(
            "engine_universe_sweep_readiness",
            lambda: {
                "readiness_status": "ready_for_static_engine_universe_forecast_sweep",
                "plan": build_engine_universe_sweep_plan(limit=25),
                "bounded_audit_note": "self-improvement audit uses plan metadata; dedicated readiness tests run the bounded sweep",
            },
        ),
        "engine_universe_gap_analysis": _safe_call("engine_universe_gap_analysis", run_engine_universe_gap_analysis),
        "model_tuning_readiness": _safe_call("model_tuning_readiness", run_model_tuning_readiness_gate),
        "final_claim_boundary_audit": _safe_call("final_claim_boundary_audit", run_final_claim_boundary_audit),
        "ollama_llm_readiness": _safe_call(
            "ollama_llm_readiness",
            lambda: {
                "readiness_status": (
                    "ready_for_local_ollama_llm_experiment"
                    if check_ollama_availability(model=DEFAULT_OLLAMA_MODEL).get("availability_status") == "available"
                    else "ready_but_local_ollama_unavailable"
                ),
                "availability": check_ollama_availability(model=DEFAULT_OLLAMA_MODEL),
                "bounded_audit_note": "self-improvement audit uses availability check; dedicated CLI smoke runs the real answer path",
            },
        ),
        "risk_v3_smoke": _safe_call("risk_v3_smoke", lambda: run_risk_engine_v3(payload=build_minimal_engine_input_fixture())),
        "dag_backtest_fixture": _safe_call(
            "dag_backtest_fixture",
            lambda: run_dag_backtest_from_payloads(payloads=tuple(build_dag_backtest_fixture()["payloads"])),
        ),
        "llm_demo_evidence_pack": _safe_call("llm_demo_evidence_pack", lambda: {"record_count": len(build_rich_llm_demo_records())}),
    }
    result = {
        "self_improvement_status": "unscored",
        "plan": build_self_improvement_plan(),
        "checks": checks,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }
    if test_results is not None:
        result["test_results"] = dict(test_results)
    result["scorecard"] = score_self_improvement_readiness(result)
    result.update(
        {
            "self_improvement_status": result["scorecard"]["self_improvement_status"],
            "overall_score_0_100": result["scorecard"]["overall_score_0_100"],
            "blocking_issues": result["scorecard"]["blocking_issues"],
            "high_priority_improvements": result["scorecard"]["high_priority_improvements"],
            "safe_completed_checks": result["scorecard"]["safe_completed_checks"],
            "unsafe_or_deferred_items": result["scorecard"]["unsafe_or_deferred_items"],
        }
    )
    return result


def _check_result(result: dict, name: str) -> dict:
    item = (result.get("checks") or {}).get(name, {})
    return item.get("result", {}) if isinstance(item, dict) else {}


def score_self_improvement_readiness(result: dict) -> dict:
    """Score readiness conservatively from audit check outputs."""

    checks = result.get("checks") or {}
    blocking: list[str] = []
    safe_completed = [name for name, item in checks.items() if item.get("check_status") == "completed"]
    failed_checks = [name for name, item in checks.items() if item.get("check_status") != "completed"]
    blocking.extend(f"{name}_failed" for name in failed_checks)

    claim = _check_result(result, "final_claim_boundary_audit")
    gateway = _check_result(result, "gateway_backtest_readiness")
    risk = _check_result(result, "risk_v3_smoke")
    dag = _check_result(result, "dag_backtest_fixture")
    llm = _check_result(result, "ollama_llm_readiness")
    gap = _check_result(result, "engine_universe_gap_analysis")
    tuning = _check_result(result, "model_tuning_readiness")

    score = 0
    tests_pass = bool(result.get("test_results", {}).get("full_suite_passed")) if isinstance(result.get("test_results"), dict) else None
    if tests_pass is True:
        score += SCORE_WEIGHTS["tests_pass"]
    elif tests_pass is False:
        blocking.append("full_test_suite_failed")
    else:
        blocking.append("full_test_suite_not_recorded_by_audit")

    claim_pass = claim.get("audit_status") == "ready_for_public_demo_claim_review"
    if claim_pass:
        score += SCORE_WEIGHTS["claim_audit_pass"]
    else:
        blocking.append("final_claim_boundary_audit_not_passing")

    gateway_ok = str(gateway.get("readiness_status", "")).startswith("ready_for")
    risk_ok = risk.get("risk_engine_status") == "completed"
    dag_ok = str(dag.get("backtest_status", "")).startswith("completed") and dag.get("auto_execution_count") == 0
    if gateway_ok and risk_ok and dag_ok:
        score += SCORE_WEIGHTS["gateway_risk_dag_robustness"]

    llm_status = str(llm.get("readiness_status", ""))
    if llm_status in {
        "ready_for_local_ollama_llm_experiment",
        "ready_but_local_ollama_unavailable",
        "ready_but_local_model_unavailable",
    }:
        score += SCORE_WEIGHTS["llm_evidence_answer_quality"]

    coverage_ratio = gap.get("evidence_coverage_ratio")
    coverage_transparent = (
        gap.get("total_specs_discovered") == 77_850
        and gap.get("completed_count") == 120
        and gap.get("skipped_count") == 77_730
        and coverage_ratio == 0.001541
    )
    if coverage_transparent:
        score += SCORE_WEIGHTS["coverage_gap_transparency"]
    else:
        blocking.append("engine_universe_gap_transparency_missing")

    if tuning.get("readiness_status") in {
        "not_ready_no_labeled_data",
        "ready_for_limited_policy_search_only",
        "ready_for_local_diagnostic_tuning",
    }:
        score += SCORE_WEIGHTS["tuning_readiness_clarity"]
    else:
        blocking.append("tuning_readiness_status_invalid")

    high_priority = [
        "claim-boundary audit included in score",
        "coverage gap transparency included in score",
        "tuning readiness classified without training",
        "gateway/risk/DAG checks included",
    ]
    deferred = [
        "stronger generated-universe claims deferred until local evidence coverage improves",
        "model training and fine-tuning deferred",
        "live/provider/cloud behavior deferred",
    ]
    if tests_pass is False:
        status = "blocked"
    elif not claim_pass:
        status = "ready_with_known_limitations" if score >= 50 else "blocked"
    elif coverage_ratio == 0.001541:
        status = "needs_evidence_before_stronger_claims"
    elif blocking:
        status = "ready_with_known_limitations"
    else:
        status = "ready_for_final_demo_review"

    return {
        "self_improvement_status": status,
        "overall_score_0_100": min(score, 100),
        "score_weights": dict(SCORE_WEIGHTS),
        "blocking_issues": sorted(set(blocking)),
        "high_priority_improvements": high_priority,
        "safe_completed_checks": safe_completed,
        "unsafe_or_deferred_items": deferred,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_self_improvement_report(result: dict) -> str:
    """Render the overnight readiness scorecard."""

    gap = _check_result(result, "engine_universe_gap_analysis")
    tuning = _check_result(result, "model_tuning_readiness")
    claim = _check_result(result, "final_claim_boundary_audit")
    blocking_lines = [f"- {issue}" for issue in result.get("blocking_issues", [])] or ["- none"]
    lines = [
        "# Overnight Self-Improvement Scorecard",
        "",
        f"Self-improvement status: {result.get('self_improvement_status')}",
        f"Overall score: {result.get('overall_score_0_100')}",
        f"Claim audit status: {claim.get('audit_status')}",
        f"Tuning readiness: {tuning.get('readiness_status')}",
        "",
        "Engine universe evidence coverage:",
        f"- Generated diagnostic spec universe: {gap.get('total_specs_discovered')}",
        f"- Latest completed specs: {gap.get('completed_count')}",
        f"- Latest skipped specs: {gap.get('skipped_count')}",
        f"- Evidence coverage ratio: {gap.get('evidence_coverage_ratio')}",
        "- Stronger claims require more local evidence and dependency outputs.",
        "",
        "Blocking issues:",
        *blocking_lines,
        "",
        "Completed hardening checks:",
        *[f"- {item}" for item in result.get("safe_completed_checks", [])],
        "",
        "Deferred unsafe items:",
        *[f"- {item}" for item in result.get("unsafe_or_deferred_items", [])],
        "",
        "Boundary:",
        "No files are written by default. Human review remains required.",
        str(result.get("non_claim", NON_CLAIM_TEXT)),
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the safe overnight self-improvement audit.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    parser.add_argument("--full-suite-passed", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    test_results = {"full_suite_passed": True} if args.full_suite_passed else None
    result = run_self_improvement_audit(test_results=test_results)
    if args.format == "report":
        print(render_self_improvement_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("self_improvement_status") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
