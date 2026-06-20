from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual
from src.hackaithon_mvp.legacy_forecast_actual_adapter import convert_legacy_rows_to_forecast_actual


def test_predicted_vs_actual_style_rows_evaluate_with_real_return_magnitude():
    converted = convert_legacy_rows_to_forecast_actual(
        (
            {
                "timestamp": "2026-03-13T09:00:00",
                "ticker": "ACB",
                "frequency": "hourly",
                "horizon": "1",
                "model": "xgboost",
                "actual_return": "0.002",
                "predicted_return": "0.3",
            },
            {
                "timestamp": "2026-03-13T10:00:00",
                "ticker": "ACB",
                "frequency": "hourly",
                "horizon": "1",
                "model": "xgboost",
                "actual_return": "-0.002",
                "predicted_return": "0.3",
            },
        )
    )

    evaluation = evaluate_forecast_vs_actual(converted, top_k=1)

    assert evaluation["rows_total"] == 2
    assert evaluation["eligible_directional_rows"] == 2
    assert evaluation["directional_accuracy"] == 0.5
    assert evaluation["by_timeframe"]["1h"]["rows_total"] == 2
    assert evaluation["by_model_family"]["xgboost"]["rows_total"] == 2


def test_frequency_timeframe_keeps_horizon_steps_separate():
    converted = convert_legacy_rows_to_forecast_actual(
        (
            {
                "timestamp": "2026-03-13T09:00:00",
                "ticker": "ACB",
                "frequency": "hourly",
                "horizon": "4",
                "actual_return": "0.002",
                "predicted_return": "0.3",
            },
        )
    )

    assert converted[0]["timeframe"] == "1h"
    assert converted[0]["horizon_steps"] == 4


def test_no_fake_actual_labels_are_created_when_actual_direction_is_missing():
    converted = convert_legacy_rows_to_forecast_actual(
        (
            {
                "ticker": "ACB",
                "datetime": "2025-01-02",
                "horizon": "40",
                "y_true": "1",
                "y_pred": "1",
            },
        ),
        default_timeframe="40d",
    )

    assert converted[0]["actual_direction_label"] == "positive"
    assert converted[0]["actual_return_magnitude_unavailable_direction_only"] is True
