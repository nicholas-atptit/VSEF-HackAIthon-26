import json
import subprocess
import sys

from src.hackaithon_mvp.feedback_loop_contract import (
    build_feedback_loop_contract,
    build_policy_update_candidate,
    validate_feedback_loop_boundary,
)


def test_feedback_loop_contract_blocks_automatic_changes():
    contract = build_feedback_loop_contract()

    assert contract["auto_apply_allowed"] is False
    assert contract["automatic_policy_update"] is False
    assert contract["training_triggered"] is False
    assert contract["inference_triggered"] is False
    assert contract["benchmark_rerun"] is False
    assert contract["live_data_enabled"] is False
    assert contract["provider_calls_enabled"] is False


def test_feedback_loop_candidate_requires_human_review_and_cannot_auto_apply():
    candidate = build_policy_update_candidate(
        evaluation_summary={
            "evaluation_status": "completed",
            "directional_accuracy": 0.48,
            "coverage_ratio": 0.75,
        },
        current_policy_id="policy.demo",
    )

    assert candidate["candidate_action"] == "review_thresholds"
    assert candidate["requires_human_review"] is True
    assert candidate["auto_apply_allowed"] is False
    assert candidate["training_triggered"] is False
    assert candidate["inference_triggered"] is False
    assert validate_feedback_loop_boundary(candidate)["is_valid"] is True


def test_feedback_loop_candidate_handles_insufficient_evidence():
    candidate = build_policy_update_candidate(
        evaluation_summary={
            "evaluation_status": "missing",
            "directional_accuracy": None,
            "coverage_ratio": None,
        },
    )

    assert candidate["candidate_action"] == "insufficient_evidence"
    assert validate_feedback_loop_boundary(candidate)["is_valid"] is True


def test_feedback_loop_contract_cli_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.feedback_loop_contract"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout)["validation"]["is_valid"] is True
