from src.hackaithon_mvp.actual_outcome_builder import build_actual_outcomes
from src.hackaithon_mvp.end_to_end_demo import (
    build_demo_bar_rows,
    build_demo_forecast_rows,
    run_end_to_end_demo,
)
from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual


def test_demo_forecast_rows_are_deterministic_and_valid():
    rows = build_demo_forecast_rows()

    assert rows == build_demo_forecast_rows()
    assert len(rows) == 1
    assert rows[0]["ticker"] == "DEMO"
    assert rows[0]["timeframe"] == "1d"
    assert rows[0]["horizon_steps"] == 1
    assert rows[0]["forecast_diagnostic"] == "positive_bias"


def test_demo_bar_rows_are_deterministic_and_valid():
    rows = build_demo_bar_rows()

    assert rows == build_demo_bar_rows()
    assert len(rows) == 2
    assert rows[0]["timestamp"] == "2026-01-01T00:00:00+07:00"
    assert rows[1]["close"] > rows[0]["close"]


def test_demo_fixture_builds_actual_outcome_and_evaluation():
    actual_rows = build_actual_outcomes(build_demo_forecast_rows(), build_demo_bar_rows())
    evaluation = evaluate_forecast_vs_actual(actual_rows)

    assert len(actual_rows) == 1
    assert actual_rows[0]["actual_direction_label"] == "positive"
    assert round(actual_rows[0]["actual_future_return"], 6) == 0.02
    assert evaluation["actual_data_status"] == "provided"
    assert evaluation["directional_accuracy"] == 1.0


def test_end_to_end_demo_completes_without_persistence():
    summary = run_end_to_end_demo()

    assert summary["demo_status"] == "completed"
    assert summary["dag_execution_status"] == "completed_with_warnings"
    assert summary["forecast_rows_total"] == 1
    assert summary["bar_rows_total"] == 2
    assert summary["actual_outcome_rows"] == 1
    assert summary["evaluation_status"] == "completed"
    assert summary["directional_accuracy"] == 1.0
    assert summary["coverage_ratio"] == 1.0
    assert summary["storage_write_enabled"] is False
    assert summary["records_written"] == 0


def test_end_to_end_demo_accepts_policy_demo_h40():
    summary = run_end_to_end_demo(policy_demo="h40")

    assert summary["demo_status"] == "completed"
    assert summary["policy_demo"] == "h40"
    assert summary["policy_metadata"]["policy_id"] == "quant_core_policy.h40.eligible_slice_gate.v1"
