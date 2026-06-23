from datetime import date, timedelta

from src.hackaithon_mvp.forecast_60pct_release_gate import (
    STATUS_BLOCKED_BELOW,
    STATUS_BLOCKED_REUSE,
    STATUS_GLOBAL,
    STATUS_SELECTIVE,
    evaluate_60pct_release_gate,
    evaluate_60pct_slice_gate,
    render_60pct_gate_report,
)


def _rows(count=320, *, correct_ratio=0.65, ticker="AAA", horizon=1):
    start = date(2025, 1, 1)
    correct_cutoff = int(count * correct_ratio)
    rows = []
    for index in range(count):
        actual = "up" if index % 2 == 0 else "down"
        predicted = actual if index < correct_cutoff else ("down" if actual == "up" else "up")
        rows.append(
            {
                "ticker": ticker,
                "model_id": "m1",
                "model_family": "classification",
                "horizon": horizon,
                "forecast_timestamp": (start + timedelta(days=index)).isoformat(),
                "actual_timestamp": (start + timedelta(days=index + horizon)).isoformat(),
                "predicted_direction": predicted,
                "actual_direction": actual,
                "actual_return": 0.01 if actual == "up" else -0.01,
            }
        )
    return rows


def test_global_60pct_release_gate_passes_only_with_rows_coverage_and_baselines():
    result = evaluate_60pct_release_gate(
        {
            "final_holdout_accuracy": 0.61,
            "final_holdout_balanced_accuracy": 0.61,
            "final_holdout_mcc": 0.22,
            "final_holdout_rows": 1200,
            "final_holdout_coverage": 0.8,
            "baseline_comparison": {
                "random_50_50_baseline_accuracy": 0.5,
                "majority_class_baseline_accuracy": 0.52,
                "previous_direction_baseline_accuracy": 0.55,
            },
        }
    )

    assert result["forecast_release_status"] == STATUS_GLOBAL
    assert result["global_release_passed"] is True
    assert result["broad_performance_claim_allowed"] is True


def test_selective_60pct_gate_passes_with_disclosed_retained_coverage():
    result = evaluate_60pct_release_gate(
        {
            "retained_holdout_accuracy": 0.602,
            "retained_holdout_balanced_accuracy": 0.615,
            "retained_holdout_mcc": 0.18,
            "retained_rows": 650,
            "retained_coverage": 0.12,
            "retained_baselines": {"random": 0.5, "majority": 0.59, "previous_direction": 0.64},
        }
    )

    assert result["forecast_release_status"] == STATUS_SELECTIVE
    assert result["selective_release_passed"] is True
    assert result["broad_performance_claim_allowed"] is False


def test_below_60pct_is_blocked_even_if_previous_search_found_edge():
    result = evaluate_60pct_release_gate(
        {
            "retained_holdout_accuracy": 0.557035,
            "retained_holdout_balanced_accuracy": 0.557273,
            "retained_holdout_mcc": 0.116346,
            "retained_rows": 3305,
            "retained_coverage": 0.208926,
            "retained_baselines": {"random": 0.5, "majority": 0.501362, "previous_direction": 0.490502},
        }
    )
    report = render_60pct_gate_report(result)

    assert result["forecast_release_status"] == STATUS_BLOCKED_BELOW
    assert result["forecast_release_allowed"] is False
    assert "60% Forecast Release Gate" in report


def test_holdout_reuse_blocks_release():
    result = evaluate_60pct_release_gate(
        {
            "final_holdout_accuracy": 0.8,
            "final_holdout_balanced_accuracy": 0.8,
            "final_holdout_mcc": 0.5,
            "final_holdout_rows": 1500,
            "final_holdout_coverage": 1.0,
            "baseline_comparison": {"random_50_50_baseline_accuracy": 0.5, "majority_class_baseline_accuracy": 0.55},
            "hidden_post_hoc_tuning_on_holdout": True,
        }
    )

    assert result["forecast_release_status"] == STATUS_BLOCKED_REUSE


def test_slice_gate_reports_preferred_and_exploratory_slices():
    preferred = _rows(320, correct_ratio=0.7, ticker="AAA")
    exploratory = _rows(180, correct_ratio=0.7, ticker="BBB")
    weak = _rows(320, correct_ratio=0.5, ticker="CCC")

    result = evaluate_60pct_slice_gate(preferred + exploratory + weak)

    assert result["passed_slice_count"] == 1
    assert result["exploratory_slice_count"] == 1
    assert result["best_slice"]["balanced_accuracy"] >= 0.6
