import pytest

from src.hackaithon_mvp.forecast_actual_evaluation import (
    derive_actual_direction_label,
    validate_forecast_actual_row,
)


def _row(**overrides):
    payload = {
        "ticker": "VCB",
        "timeframe": "1 ngày",
        "prediction_timestamp": "2026-01-01T09:00:00",
        "horizon_steps": 1,
        "forecast_diagnostic": "positive_bias",
        "actual_future_return": 0.01,
        "actual_direction_label": "positive",
    }
    payload.update(overrides)
    return payload


def test_valid_row_passes_and_normalizes_timeframe():
    row = validate_forecast_actual_row(_row())

    assert row["ticker"] == "VCB"
    assert row["timeframe"] == "1d"
    assert row["horizon_steps"] == 1


def test_invalid_timeframe_rejected():
    with pytest.raises(ValueError, match="unsupported timeframe"):
        validate_forecast_actual_row(_row(timeframe="3m"))


def test_missing_required_fields_rejected():
    payload = _row()
    payload.pop("prediction_timestamp")

    with pytest.raises(ValueError, match="missing required"):
        validate_forecast_actual_row(payload)


@pytest.mark.parametrize(
    ("actual_return", "expected_label"),
    [(0.01, "positive"), (-0.01, "negative"), (0.0, "flat")],
)
def test_actual_label_derives_from_return_when_blank(actual_return, expected_label):
    row = validate_forecast_actual_row(_row(actual_future_return=actual_return, actual_direction_label=""))

    assert row["actual_direction_label"] == expected_label
    assert derive_actual_direction_label(actual_return) == expected_label


def test_horizon_steps_must_be_positive():
    with pytest.raises(ValueError, match="horizon_steps"):
        validate_forecast_actual_row(_row(horizon_steps=0))
