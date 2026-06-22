from src.hackaithon_mvp.forecast_accuracy_evaluator import (
    evaluate_directional_accuracy,
    evaluate_forecast_accuracy,
    evaluate_numeric_forecast_error,
    evaluate_probability_metrics,
    normalize_forecast_actual_rows,
    render_forecast_accuracy_report,
)


def _row(index, predicted, actual, probability=0.6, predicted_return=0.01, actual_return=0.01, model_id="m1"):
    return {
        "symbol": "AAA" if index % 2 == 0 else "BBB",
        "model_key": model_id,
        "model_family": "classification",
        "horizon_steps": 1 if index < 6 else 5,
        "asof": f"2026-01-{index + 1:02d}T09:00:00",
        "y_pred": predicted,
        "y_true": actual,
        "prob_up": probability,
        "forecast_return": predicted_return,
        "realized_return": actual_return,
    }


def test_perfect_predictions_have_full_directional_accuracy():
    rows = [_row(0, "up", "up"), _row(1, "down", "down")]

    result = evaluate_directional_accuracy(rows)

    assert result["coverage_count"] == 2
    assert result["accuracy"] == 1.0
    assert result["balanced_accuracy"] == 1.0
    assert result["confusion_matrix"]["actual_up"]["predicted_up"] == 1
    assert result["mcc"] == 1.0


def test_all_wrong_predictions_have_zero_accuracy():
    result = evaluate_directional_accuracy([_row(0, "up", "down"), _row(1, "down", "up")])

    assert result["accuracy"] == 0.0
    assert result["balanced_accuracy"] == 0.0
    assert result["mcc"] == -1.0


def test_imbalanced_labels_report_balanced_accuracy():
    rows = [
        _row(0, "up", "up"),
        _row(1, "up", "up"),
        _row(2, "up", "up"),
        _row(3, "up", "down"),
    ]

    result = evaluate_directional_accuracy(rows)

    assert result["accuracy"] == 0.75
    assert result["balanced_accuracy"] == 0.5
    assert result["positive_actual_count"] == 3
    assert result["negative_actual_count"] == 1


def test_missing_numeric_returns_do_not_fabricate_numeric_metrics():
    rows = [{"ticker": "AAA", "predicted_direction": "up", "actual_direction": "up"}]

    result = evaluate_numeric_forecast_error(rows)

    assert result["numeric_coverage_count"] == 0
    assert result["mae"] is None


def test_numeric_and_probability_metrics_are_computed():
    rows = [
        _row(i, "up" if i % 2 == 0 else "down", "up" if i % 2 == 0 else "down", probability=0.8 if i % 2 == 0 else 0.2)
        for i in range(10)
    ]

    numeric = evaluate_numeric_forecast_error(rows)
    probability = evaluate_probability_metrics(rows)

    assert numeric["numeric_coverage_count"] == 10
    assert numeric["mae"] == 0.0
    assert probability["probability_coverage_count"] == 10
    assert probability["brier_score"] < 0.05
    assert probability["log_loss"] < 0.25
    assert probability["calibration_bins"]


def test_grouped_metrics_and_baselines_are_present():
    rows = [
        _row(i, "up" if i % 2 == 0 else "down", "up" if i % 3 else "down", model_id="m1" if i < 6 else "m2")
        for i in range(12)
    ]

    result = evaluate_forecast_accuracy(rows)

    assert result["accuracy_status"] == "evaluated_local_forecast_actual_rows"
    assert "ticker=AAA" in result["groups"]["by_ticker"]
    assert "horizon=1" in result["groups"]["by_horizon"]
    assert "model_id=m1" in result["groups"]["by_model_id"]
    assert result["baseline_comparison"]["majority_class_baseline_accuracy"] is not None
    assert result["baseline_comparison"]["random_50_50_baseline_accuracy"] == 0.5


def test_no_rows_and_malformed_rows_do_not_invent_accuracy():
    result = evaluate_forecast_accuracy([])
    malformed = normalize_forecast_actual_rows([{"ticker": "AAA"}, "bad"])

    assert result["accuracy_status"] == "not_ready_no_forecast_actual_rows"
    assert result["global"]["directional"]["accuracy"] is None
    assert malformed == ()


def test_wilson_interval_is_bounded():
    result = evaluate_directional_accuracy([_row(i, "up", "up") for i in range(10)])

    interval = result["wilson_accuracy_interval"]
    assert 0.0 <= interval["lower"] <= interval["upper"] <= 1.0
    assert interval["upper"] == 1.0


def test_report_has_no_market_action_labels():
    result = evaluate_forecast_accuracy([_row(0, "up", "up"), _row(1, "down", "down")])
    report = render_forecast_accuracy_report(result).lower()

    for forbidden in ("buy", "sell", "hold"):
        assert forbidden not in report
