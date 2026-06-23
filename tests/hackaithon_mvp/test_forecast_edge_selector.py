from datetime import date, timedelta

from src.hackaithon_mvp.forecast_accuracy_evaluator import evaluate_forecast_accuracy
from src.hackaithon_mvp.forecast_edge_selector import select_forecast_edge_slices, render_forecast_edge_selection_report


def _forecast_rows(count=360, ticker="AAA", horizon=1, correct=True):
    start = date(2025, 1, 1)
    rows = []
    for index in range(count):
        actual = "up" if index % 2 == 0 else "down"
        predicted = actual if correct else ("down" if actual == "up" else "up")
        rows.append(
            {
                "ticker": ticker,
                "model_id": "edge_model",
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


def _result(rows, ticker="AAA", horizon=1, minimum_holdout_rows=300):
    metrics = evaluate_forecast_accuracy(rows)
    return {
        "slice_id": f"{ticker}|h{horizon}|edge_model",
        "ticker": ticker,
        "horizon": horizon,
        "model_id": "edge_model",
        "holdout_rows": len(rows),
        "minimum_holdout_rows": minimum_holdout_rows,
        "validation_metrics": {"balanced_accuracy": 0.7, "mcc": 0.4},
        "holdout_metrics": metrics["global"]["directional"],
        "holdout_baselines": metrics["baseline_comparison"],
        "holdout_forecast_rows": rows,
        "duplicate_key_severity": "none",
        "overlap_severity": "none",
        "leakage_warning": False,
    }


def test_selector_allows_only_strict_holdout_passing_slices():
    allowed_rows = _forecast_rows()
    rejected_rows = _forecast_rows(count=360, ticker="BBB", correct=False)

    result = select_forecast_edge_slices([_result(allowed_rows), _result(rejected_rows, ticker="BBB")])

    assert result["allowed_slice_count"] == 1
    assert result["rejected_slice_count"] == 1
    assert result["retained_holdout_balanced_accuracy"] == 1.0
    assert result["beats_random"] is True
    assert result["beats_majority"] is True


def test_selector_discloses_low_rows_and_reasons():
    result = select_forecast_edge_slices([_result(_forecast_rows(count=120), minimum_holdout_rows=300)])
    report = render_forecast_edge_selection_report(result)

    assert result["allowed_slice_count"] == 0
    assert "insufficient_holdout_rows" in result["rejection_reason_distribution"]
    assert "Forecast Edge Selector" in report
