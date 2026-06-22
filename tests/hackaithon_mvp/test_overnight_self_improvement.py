import subprocess
import sys

from src.hackaithon_mvp.overnight_self_improvement import (
    build_self_improvement_plan,
    render_self_improvement_report,
    run_self_improvement_audit,
    score_self_improvement_readiness,
)


def test_self_improvement_plan_lists_required_checks():
    plan = build_self_improvement_plan()

    assert plan["plan_status"] == "ready"
    assert "final_claim_boundary_audit" in plan["checks"]
    assert "engine_universe_gap_analysis" in plan["checks"]
    assert plan["writes_files_by_default"] is False


def test_score_mentions_low_coverage_and_does_not_overstate_readiness():
    result = {
        "checks": {
            "final_claim_boundary_audit": {
                "check_status": "completed",
                "result": {"audit_status": "ready_for_public_demo_claim_review"},
            },
            "gateway_backtest_readiness": {
                "check_status": "completed",
                "result": {"readiness_status": "ready_for_offline_gateway_backtest_and_fine_tune_control"},
            },
            "risk_v3_smoke": {"check_status": "completed", "result": {"risk_engine_status": "completed"}},
            "dag_backtest_fixture": {
                "check_status": "completed",
                "result": {"backtest_status": "completed", "auto_execution_count": 0},
            },
            "ollama_llm_readiness": {
                "check_status": "completed",
                "result": {"readiness_status": "ready_for_local_ollama_llm_experiment"},
            },
            "engine_universe_gap_analysis": {
                "check_status": "completed",
                "result": {
                    "total_specs_discovered": 77_850,
                    "completed_count": 120,
                    "skipped_count": 77_730,
                    "evidence_coverage_ratio": 0.001541,
                },
            },
            "model_tuning_readiness": {
                "check_status": "completed",
                "result": {"readiness_status": "not_ready_no_labeled_data"},
            },
        },
        "test_results": {"full_suite_passed": True},
    }

    score = score_self_improvement_readiness(result)

    assert score["overall_score_0_100"] == 100
    assert score["self_improvement_status"] == "needs_evidence_before_stronger_claims"


def test_self_improvement_audit_runs_and_report_renders():
    result = run_self_improvement_audit(test_results={"full_suite_passed": True})
    report = render_self_improvement_report(result)

    assert "overall_score_0_100" in result
    assert "Engine universe evidence coverage" in report
    assert "Evidence coverage ratio" in report
    assert result["overall_score_0_100"] == 100
    assert result["self_improvement_status"] == "needs_evidence_before_stronger_claims"


def test_overnight_self_improvement_cli_report_runs():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.overnight_self_improvement", "--format", "report"],
        capture_output=True,
        text=True,
    )

    assert "Overnight Self-Improvement Scorecard" in completed.stdout
    assert completed.returncode in {0, 1}


def test_overnight_self_improvement_cli_accepts_external_test_pass_flag():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.overnight_self_improvement",
            "--full-suite-passed",
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Overall score: 100" in completed.stdout
