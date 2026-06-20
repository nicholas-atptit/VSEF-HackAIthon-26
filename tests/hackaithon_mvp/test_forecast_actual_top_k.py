from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual

from forecast_actual_fixtures import forecast_actual_rows


def test_top_k_metrics_are_calculated_from_ranked_directional_rows():
    evaluation = evaluate_forecast_vs_actual(forecast_actual_rows(), top_k=2)
    top_k = evaluation["top_k_summary"]

    assert top_k["top_k"] == 2
    assert top_k["selected_rows"] == 2
    assert top_k["rows_total"] == 2
    assert top_k["eligible_directional_rows"] == 2
    assert top_k["directional_accuracy"] == 0.5


def test_top_k_sorting_is_deterministic_for_ties():
    rows = (
        {
            "ticker": "BID",
            "timeframe": "1d",
            "prediction_timestamp": "2026-01-01T09:00:00",
            "horizon_steps": 1,
            "forecast_diagnostic": "positive_bias",
            "actual_future_return": 0.01,
            "actual_direction_label": "positive",
            "engine_id": "b",
            "diagnostic_score": 0.9,
            "confidence": 0.5,
        },
        {
            "ticker": "ACB",
            "timeframe": "1d",
            "prediction_timestamp": "2026-01-01T09:00:00",
            "horizon_steps": 1,
            "forecast_diagnostic": "positive_bias",
            "actual_future_return": -0.01,
            "actual_direction_label": "negative",
            "engine_id": "a",
            "diagnostic_score": 0.9,
            "confidence": 0.5,
        },
    )

    evaluation = evaluate_forecast_vs_actual(rows, top_k=1)
    assert evaluation["top_k_summary"]["directional_accuracy"] == 0.0
