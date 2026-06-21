import subprocess
import sys

from src.hackaithon_mvp.dag_backtest_harness import build_dag_backtest_fixture, run_dag_backtest_from_payloads
from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.fine_tune_control_plane import (
    assess_fine_tune_readiness,
    build_fine_tune_control_policy,
    build_fine_tune_experiment_candidate,
    validate_fine_tune_candidate,
)


def test_fine_tune_control_policy_never_trains_by_default():
    policy = build_fine_tune_control_policy()

    assert policy["auto_training_allowed"] is False
    assert policy["auto_deploy_allowed"] is False
    assert policy["provider_calls_allowed"] is False
    assert policy["human_review_required"] is True


def test_fine_tune_candidate_requires_human_review_and_no_auto_mutation():
    payload = build_minimal_engine_input_fixture()
    engine_result = run_diagnostic_engine_from_payload(payload)
    backtest = run_dag_backtest_from_payloads(payloads=tuple(build_dag_backtest_fixture()["payloads"]))
    readiness = assess_fine_tune_readiness(
        engine_result=engine_result,
        backtest_result=backtest,
        ml_summary=engine_result["ml_engine"],
    )
    candidate = build_fine_tune_experiment_candidate(readiness=readiness)
    validation = validate_fine_tune_candidate(candidate)

    assert candidate["candidate_status"] == "draft_for_human_review"
    assert candidate["human_review_required"] is True
    assert candidate["auto_training_allowed"] is False
    assert candidate["auto_deploy_allowed"] is False
    assert candidate["provider_calls_allowed"] is False
    assert candidate["policy_mutation_allowed"] is False
    assert validation["is_valid"] is True


def test_fine_tune_readiness_handles_missing_inputs():
    readiness = assess_fine_tune_readiness()
    candidate = build_fine_tune_experiment_candidate(readiness=readiness)

    assert readiness["readiness_level"] == "not_ready"
    assert "engine_result_required" in readiness["blocking_reasons"]
    assert "insufficient_data_for_fine_tune" in candidate["recommended_review_actions"]


def test_fine_tune_control_plane_cli_report_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.fine_tune_control_plane", "--format", "report"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Fine-tune Control Plane" in completed.stdout
    assert "Auto training allowed: False" in completed.stdout
