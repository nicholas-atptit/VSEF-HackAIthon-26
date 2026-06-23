from datetime import date, timedelta

from src.hackaithon_mvp.forecast_edge_model_trainer import train_forecast_edge_models, render_forecast_edge_training_report


def _rows(count=420):
    start = date(2025, 1, 1)
    rows = []
    for index in range(count):
        value = 1.0 if index % 2 == 0 else -1.0
        direction = "up" if value > 0 else "down"
        rows.append(
            {
                "ticker": "AAA",
                "horizon": 1,
                "timestamp": (start + timedelta(days=index)).isoformat(),
                "forecast_timestamp": (start + timedelta(days=index)).isoformat(),
                "actual_timestamp": (start + timedelta(days=index + 1)).isoformat(),
                "feature_predictive": value,
                "feature_noise": float(index % 7),
                "future_direction": direction,
                "actual_direction": direction,
                "future_return": 0.01 if direction == "up" else -0.01,
            }
        )
    return rows


def test_edge_model_trainer_trains_bounded_models():
    result = train_forecast_edge_models(_rows(), horizons=(1,), max_models=4, max_workers=1, min_slice_rows=120)
    report = render_forecast_edge_training_report(result)

    assert result["training_status"] == "completed"
    assert result["attempted_model_specs"] >= 1
    assert result["trained_model_specs"] >= 1
    assert result["forecast_rows_count"] > 0
    assert "Forecast Edge Model Trainer" in report


def test_edge_model_trainer_abstains_when_rows_are_missing():
    result = train_forecast_edge_models([], horizons=(1,), max_models=2, max_workers=1)

    assert result["training_status"] == "blocked_by_insufficient_data"
    assert result["trained_model_specs"] == 0
