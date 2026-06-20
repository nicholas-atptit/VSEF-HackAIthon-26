from src.hackaithon_mvp.actual_outcome_builder import build_actual_outcomes, derive_actual_label
from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual


def _forecast(timestamp="2026-01-01T00:00:00+07:00", horizon=1, diagnostic="positive_bias"):
    return {
        "ticker": "VCB",
        "timeframe": "1d",
        "prediction_timestamp": timestamp,
        "horizon_steps": horizon,
        "forecast_diagnostic": diagnostic,
    }


def _bars(future_close):
    return (
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "timestamp": "2026-01-01T00:00:00+07:00",
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10,
            "volume": 100,
        },
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "timestamp": "2026-01-02T00:00:00+07:00",
            "open": future_close,
            "high": max(future_close, 10),
            "low": min(future_close, 10),
            "close": future_close,
            "volume": 100,
        },
    )


def test_positive_future_return_derives_positive():
    rows = build_actual_outcomes((_forecast(),), _bars(12))

    assert round(rows[0]["actual_future_return"], 6) == 0.2
    assert rows[0]["actual_direction_label"] == "positive"
    assert derive_actual_label(rows[0]["actual_future_return"]) == "positive"


def test_negative_future_return_derives_negative():
    rows = build_actual_outcomes((_forecast(diagnostic="negative_bias"),), _bars(8))

    assert round(rows[0]["actual_future_return"], 6) == -0.2
    assert rows[0]["actual_direction_label"] == "negative"


def test_zero_future_return_derives_flat():
    rows = build_actual_outcomes((_forecast(diagnostic="neutral_or_uncertain"),), _bars(10))

    assert rows[0]["actual_future_return"] == 0
    assert rows[0]["actual_direction_label"] == "flat"


def test_output_rows_are_accepted_by_forecast_actual_evaluator():
    rows = build_actual_outcomes((_forecast(), _forecast(diagnostic="negative_bias")), _bars(12))
    evaluation = evaluate_forecast_vs_actual(rows)

    assert evaluation["actual_data_status"] == "provided"
    assert evaluation["rows_total"] == 2
    assert evaluation["eligible_directional_rows"] == 2
