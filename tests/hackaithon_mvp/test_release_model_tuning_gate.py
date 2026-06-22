import re

from src.hackaithon_mvp.release_model_tuning_gate import (
    inspect_tuning_eligibility,
    render_release_model_tuning_gate_report,
    run_release_model_tuning_gate,
)


def _rows(count=12, *, probability=True, feature=False, duplicate=False):
    rows = []
    for index in range(count):
        row = {
            "ticker": "AAA",
            "model_id": "model-a",
            "model_family": "classification",
            "horizon": 1,
            "forecast_timestamp": "2026-01-01T09:00:00" if duplicate else f"2026-01-{index + 1:02d}T09:00:00",
            "predicted_direction": "up" if index % 2 == 0 else "down",
            "actual_direction": "up" if index % 3 else "down",
        }
        if probability:
            row["predicted_probability"] = 0.7 if row["predicted_direction"] == "up" else 0.3
        if feature:
            row["feature_momentum"] = index / 10
        rows.append(row)
    return rows


def test_no_labeled_rows_are_not_ready():
    result = run_release_model_tuning_gate([])

    assert result["tuning_gate_status"] == "not_ready_no_labeled_data"
    assert "missing_labeled_forecast_actual_rows" in result["eligibility"]["skip_reasons"]


def test_insufficient_rows_are_not_ready():
    result = run_release_model_tuning_gate(_rows(5))

    assert result["tuning_gate_status"] == "not_ready_insufficient_rows"
    assert "insufficient_global_labeled_rows" in result["eligibility"]["skip_reasons"]


def test_forecast_outputs_with_scores_are_ready_for_policy_threshold_tuning():
    result = run_release_model_tuning_gate(_rows(12, probability=True))

    assert result["tuning_gate_status"] == "ready_for_policy_threshold_tuning"
    assert result["allowed_tuning_scope"] == "policy_threshold_only"
    assert result["training_ran"] is False


def test_rows_without_scores_are_evaluation_only():
    result = run_release_model_tuning_gate(_rows(12, probability=False))

    assert result["tuning_gate_status"] == "ready_for_release_evaluation_only"


def test_feature_rows_are_ready_for_hyperparameter_gate_only():
    result = run_release_model_tuning_gate(_rows(12, probability=True, feature=True))

    assert result["tuning_gate_status"] == "ready_for_model_hyperparameter_tuning"
    assert result["training_ran"] is False
    assert result["eligibility"]["feature_columns"] == ["feature_momentum"]


def test_duplicate_identity_collisions_block_tuning():
    result = run_release_model_tuning_gate(_rows(12, duplicate=True))

    assert result["tuning_gate_status"] == "not_ready_insufficient_rows"
    assert "duplicate_forecast_identity_collisions" in result["eligibility"]["skip_reasons"]


def test_inspection_and_report_are_public_safe():
    eligibility = inspect_tuning_eligibility(_rows(12))
    report = render_release_model_tuning_gate_report(run_release_model_tuning_gate(_rows(12))).lower()

    assert eligibility["checks"]["human_review_required"] is True
    assert "Release Model Tuning Gate" in render_release_model_tuning_gate_report(run_release_model_tuning_gate(_rows(12)))
    for forbidden in ("buy", "sell", "hold"):
        assert re.search(rf"\b{forbidden}\b", report) is None
