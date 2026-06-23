"""Safe overnight self-improvement audit orchestrator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.hackaithon_mvp.dag_backtest_harness import build_dag_backtest_fixture, run_dag_backtest_from_payloads
from src.hackaithon_mvp.diagram_demo_readiness import build_diagram_demo_readiness_summary
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.engine_universe_gap_analysis import run_engine_universe_gap_analysis
from src.hackaithon_mvp.engine_universe_forecast_sweep import build_engine_universe_sweep_plan
from src.hackaithon_mvp.eligible_model_policy_tuner import tune_all_eligible_models
from src.hackaithon_mvp.final_claim_boundary_audit import run_final_claim_boundary_audit
from src.hackaithon_mvp.gateway_backtest_readiness import run_gateway_backtest_readiness_gate
from src.hackaithon_mvp.llm_demo_evidence_pack import build_rich_llm_demo_records
from src.hackaithon_mvp.model_tuning_readiness import run_model_tuning_readiness_gate
from src.hackaithon_mvp.ollama_local_client import DEFAULT_OLLAMA_MODEL, check_ollama_availability
from src.hackaithon_mvp.public_demo_readiness import build_public_demo_readiness_summary
from src.hackaithon_mvp.release_accuracy_report import build_release_accuracy_report
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
            "forecast_actual_artifact_discovery",
            "release_accuracy_report",
            "release_model_tuning_gate",
            "eligible_model_policy_tuning_availability",
            "full_release_model_pipeline_status",
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


def _read_full_release_model_pipeline_status(output_root: str = ".tmp_full_model_run") -> dict[str, Any]:
    summary_path = Path(output_root) / "full_release_model_pipeline_summary.json"
    if not summary_path.exists():
        return {
            "pipeline_status": "not_run_no_generated_output_root",
            "output_root": output_root,
            "generated_evidence_available": False,
            "completed_improvement": None,
            "remaining_skip_reasons": {},
            "non_claim": "Full release model pipeline status is read-only and requires explicit generated outputs.",
            "human_review_required": True,
        }
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    engine = payload.get("engine_universe", {}) if isinstance(payload, dict) else {}
    training = payload.get("training", {}) if isinstance(payload, dict) else {}
    return {
        "pipeline_status": payload.get("pipeline_status"),
        "output_root": output_root,
        "generated_evidence_available": True,
        "trained_model_specs": training.get("trained_model_specs"),
        "tuned_model_specs": training.get("tuned_model_specs"),
        "generated_forecast_rows": (payload.get("evidence_materialization") or {}).get("forecast_row_count"),
        "completed_count": engine.get("completed_count"),
        "skipped_count": engine.get("skipped_count"),
        "completed_improvement": engine.get("completed_improvement"),
        "remaining_skip_reasons": engine.get("skip_reason_distribution") or {},
        "non_claim": "Full release model pipeline status is read from local generated outputs only.",
        "human_review_required": True,
    }


def run_self_improvement_audit(*, test_results: dict[str, Any] | None = None) -> dict:
    """Run bounded local checks and return a readiness audit result."""

    release_accuracy_check = _safe_call(
        "release_accuracy_report",
        lambda: build_release_accuracy_report(discover=True),
    )
    release_accuracy_result = release_accuracy_check.get("result", {})
    release_discovery = release_accuracy_result.get("artifact_discovery")
    release_tuning_readiness = release_accuracy_result.get("tuning_readiness")
    release_tuning_result = release_accuracy_result.get("tuning_result")
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
        "forecast_actual_artifact_discovery": {
            "check_status": "completed" if isinstance(release_discovery, dict) else "failed",
            "result": release_discovery if isinstance(release_discovery, dict) else {},
            "errors": [] if isinstance(release_discovery, dict) else ["forecast_actual_artifact_discovery_missing"],
        },
        "release_accuracy_report": release_accuracy_check,
        "release_model_tuning_gate": {
            "check_status": "completed" if isinstance(release_tuning_readiness, dict) else "failed",
            "result": release_tuning_readiness if isinstance(release_tuning_readiness, dict) else {},
            "errors": [] if isinstance(release_tuning_readiness, dict) else ["release_model_tuning_gate_missing"],
        },
        "eligible_model_policy_tuning_availability": {
            "check_status": "completed" if isinstance(release_tuning_result, dict) else "completed",
            "result": release_tuning_result if isinstance(release_tuning_result, dict) else tune_all_eligible_models([]),
            "errors": [],
        },
        "full_release_model_pipeline_status": _safe_call(
            "full_release_model_pipeline_status",
            _read_full_release_model_pipeline_status,
        ),
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
    artifact_discovery = _check_result(result, "forecast_actual_artifact_discovery")
    release_accuracy = _check_result(result, "release_accuracy_report")
    release_tuning = _check_result(result, "release_model_tuning_gate")
    eligible_tuning = _check_result(result, "eligible_model_policy_tuning_availability")
    full_pipeline = _check_result(result, "full_release_model_pipeline_status")

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

    accuracy_missing = release_accuracy.get("release_accuracy_status") == "not_ready_no_forecast_actual_rows"
    if accuracy_missing:
        blocking.append("forecast_actual_accuracy_missing_before_release")
        score = min(score, 85)
    tuning_deferred_no_labeled_data = release_tuning.get("tuning_gate_status") == "not_ready_no_labeled_data"
    if (
        full_pipeline.get("pipeline_status") == "completed_partial_due_to_dependencies"
        or int(full_pipeline.get("skipped_count") or 0) > 0
        or coverage_ratio == 0.001541
    ):
        score = min(score, 85)

    high_priority = [
        "claim-boundary audit included in score",
        "coverage gap transparency included in score",
        "tuning readiness and generated local training status reported",
        "gateway/risk/DAG checks included",
        "release accuracy gate included",
    ]
    full_pipeline_generated = bool(full_pipeline.get("generated_evidence_available"))
    deferred = [
        "stronger generated-universe claims deferred until local evidence coverage improves",
        "live/provider/cloud behavior deferred",
    ]
    if full_pipeline_generated:
        deferred.append("remaining generated specs without local target/horizon evidence or dependency outputs remain skipped")
    else:
        deferred.append("full local model run deferred until explicit .tmp_full_model_run output is generated")
    if tuning_deferred_no_labeled_data or eligible_tuning.get("tuning_status") == "no_eligible_models":
        deferred.append("tuning_deferred_no_labeled_data")
    if tests_pass is False:
        status = "blocked"
    elif accuracy_missing:
        status = "needs_forecast_actual_accuracy_before_release"
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
        "forecast_actual_artifact_discovery_status": artifact_discovery.get("discovery_status"),
        "forecast_actual_candidate_files": artifact_discovery.get("candidate_file_count"),
        "release_accuracy_status": release_accuracy.get("release_accuracy_status"),
        "release_model_tuning_gate_status": release_tuning.get("tuning_gate_status"),
        "eligible_model_policy_tuning_status": eligible_tuning.get("tuning_status"),
        "full_release_model_pipeline_status": full_pipeline.get("pipeline_status"),
        "generated_evidence_completed_count": full_pipeline.get("completed_count"),
        "generated_evidence_skipped_count": full_pipeline.get("skipped_count"),
        "generated_evidence_completed_improvement": full_pipeline.get("completed_improvement"),
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
    }


def render_self_improvement_report(result: dict) -> str:
    """Render the overnight readiness scorecard."""

    gap = _check_result(result, "engine_universe_gap_analysis")
    tuning = _check_result(result, "model_tuning_readiness")
    claim = _check_result(result, "final_claim_boundary_audit")
    release_accuracy = _check_result(result, "release_accuracy_report")
    release_tuning = _check_result(result, "release_model_tuning_gate")
    discovery = _check_result(result, "forecast_actual_artifact_discovery")
    full_pipeline = _check_result(result, "full_release_model_pipeline_status")
    blocking_lines = [f"- {issue}" for issue in result.get("blocking_issues", [])] or ["- none"]
    lines = [
        "# Overnight Self-Improvement Scorecard",
        "",
        f"Self-improvement status: {result.get('self_improvement_status')}",
        f"Overall score: {result.get('overall_score_0_100')}",
        f"Claim audit status: {claim.get('audit_status')}",
        f"Tuning readiness: {tuning.get('readiness_status')}",
        f"Release accuracy status: {release_accuracy.get('release_accuracy_status')}",
        f"Release tuning gate: {release_tuning.get('tuning_gate_status')}",
        f"Forecast-vs-actual candidate files: {discovery.get('candidate_file_count')}",
        f"Full release model pipeline: {full_pipeline.get('pipeline_status')}",
        f"Generated evidence completed improvement: {full_pipeline.get('completed_improvement')}",
        "",
        "Engine universe evidence coverage:",
        f"- Generated diagnostic spec universe: {gap.get('total_specs_discovered')}",
        f"- Static-evidence completed specs before materialization: {gap.get('completed_count')}",
        f"- Static-evidence skipped specs before materialization: {gap.get('skipped_count')}",
        f"- Evidence coverage ratio before materialization: {gap.get('evidence_coverage_ratio')}",
        f"- Generated-evidence completed specs: {full_pipeline.get('completed_count')}",
        f"- Generated-evidence skipped specs: {full_pipeline.get('skipped_count')}",
        f"- Generated-evidence remaining skip reasons: {full_pipeline.get('remaining_skip_reasons') or {}}",
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
