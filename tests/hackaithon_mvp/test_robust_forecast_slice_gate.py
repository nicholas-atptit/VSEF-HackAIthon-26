from datetime import date, timedelta

from src.hackaithon_mvp.robust_forecast_slice_gate import (
    ABSTAIN_BELOW_RANDOM,
    ABSTAIN_INSUFFICIENT_ROWS,
    FORECAST_ALLOWED,
    build_forecast_allowed_slices,
    evaluate_slice_stability,
    render_forecast_slice_gate_report,
)


def _slice_rows(count=30, *, ticker="AAA", correct=True):
    start = date(2025, 1, 1)
    rows = []
    for index in range(count):
        actual = "up" if index % 2 == 0 else "down"
        predicted = actual if correct else ("down" if actual == "up" else "up")
        forecast_day = start + timedelta(days=index)
        rows.append(
            {
                "ticker": ticker,
                "model_id": "m1",
                "horizon": 1,
                "forecast_timestamp": forecast_day.isoformat(),
                "actual_timestamp": (forecast_day + timedelta(days=1)).isoformat(),
                "predicted_direction": predicted,
                "actual_direction": actual,
                "actual_return": 0.01 if actual == "up" else -0.01,
                "deoverlap_step_index": index,
            }
        )
    return rows


def test_evaluate_slice_stability_reports_validation_and_holdout_metrics():
    result = evaluate_slice_stability(_slice_rows())

    assert result["row_count"] == 30
    assert result["validation_rows"] > 0
    assert result["holdout_rows"] > 0
    assert result["holdout_metrics"]["balanced_accuracy"] == 1.0


def test_build_forecast_allowed_slices_allows_strong_slice():
    result = build_forecast_allowed_slices(_slice_rows(), min_rows=10)
    report = render_forecast_slice_gate_report(result)

    assert result["allowed_slice_count"] == 1
    assert result["status_counts"][FORECAST_ALLOWED] == 1
    assert "Robust Forecast Slice Gate" in report


def test_gate_abstains_for_insufficient_rows_and_below_random():
    rows = _slice_rows(8, ticker="SMALL") + _slice_rows(30, ticker="BAD", correct=False)
    result = build_forecast_allowed_slices(rows, min_rows=10)
    statuses = {item["status"] for item in result["slice_results"].values()}

    assert ABSTAIN_INSUFFICIENT_ROWS in statuses
    assert ABSTAIN_BELOW_RANDOM in statuses
    assert result["allowed_slice_count"] == 0
