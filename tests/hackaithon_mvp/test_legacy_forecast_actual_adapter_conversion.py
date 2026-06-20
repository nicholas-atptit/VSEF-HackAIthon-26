import pytest

from src.hackaithon_mvp.forecast_actual_evaluation import evaluate_forecast_vs_actual
from src.hackaithon_mvp.legacy_forecast_actual_adapter import (
    WARNING_DIRECTION_ONLY,
    WARNING_SYNTHETIC_TIMESTAMP,
    convert_legacy_rows_to_forecast_actual,
    summarize_conversion,
)


def test_y_true_y_pred_maps_directional_rows_and_placeholder_warning():
    converted = convert_legacy_rows_to_forecast_actual(
        (
            {"ticker": "VCB", "datetime": "2025-01-02", "horizon": "1", "y_true": "1", "y_pred": "1"},
            {"ticker": "BID", "datetime": "2025-01-03", "horizon": "1", "y_true": "0", "y_pred": "1"},
        ),
        default_timeframe="1d",
    )

    assert converted[0]["forecast_diagnostic"] == "positive_bias"
    assert converted[0]["actual_direction_label"] == "positive"
    assert converted[0]["actual_future_return"] == 1.0
    assert converted[0][WARNING_DIRECTION_ONLY] is True
    assert converted[1]["actual_direction_label"] == "negative"
    assert converted[1]["actual_future_return"] == -1.0


def test_actual_return_and_predicted_return_map_without_placeholder_warning():
    converted = convert_legacy_rows_to_forecast_actual(
        (
            {
                "ticker": "VCB",
                "timestamp": "2025-01-02T10:00:00",
                "frequency": "hourly",
                "horizon": "1",
                "actual_return": "-0.01",
                "predicted_return": "0.02",
                "model": "xgboost",
                "confidence": "0.7",
            },
            {
                "ticker": "VCB",
                "timestamp": "2025-01-02T11:00:00",
                "frequency": "hourly",
                "horizon": "1",
                "actual_return": "0",
                "predicted_return": "0",
            },
        )
    )

    assert converted[0]["timeframe"] == "1h"
    assert converted[0]["forecast_diagnostic"] == "positive_bias"
    assert converted[0]["actual_future_return"] == -0.01
    assert converted[0]["actual_direction_label"] == "negative"
    assert WARNING_DIRECTION_ONLY not in converted[0]
    assert converted[1]["forecast_diagnostic"] == "neutral_or_uncertain"
    assert converted[1]["actual_direction_label"] == "flat"


def test_aliases_are_supported():
    converted = convert_legacy_rows_to_forecast_actual(
        (
            {
                "ticker": "CTG",
                "date": "2025-01-02",
                "horizon_steps": "2",
                "label": "0",
                "pred": "0",
            },
        ),
        default_timeframe="2d",
    )

    assert converted[0]["forecast_diagnostic"] == "negative_bias"
    assert converted[0]["actual_direction_label"] == "negative"


def test_summarize_conversion_reports_warnings():
    converted = convert_legacy_rows_to_forecast_actual(
        ({"ticker": "VCB", "horizon": "1", "y_true": "1", "y_pred": "0"},),
        default_timeframe="1d",
        allow_row_index_timestamp=True,
    )
    summary = summarize_conversion(converted)

    assert summary["rows_total"] == 1
    assert summary["warnings"][WARNING_DIRECTION_ONLY] == 1
    assert summary["warnings"][WARNING_SYNTHETIC_TIMESTAMP] == 1
    assert summary["direction_only_placeholder_return_used"] is True


def test_converted_rows_are_accepted_by_evaluator():
    converted = convert_legacy_rows_to_forecast_actual(
        (
            {"ticker": "VCB", "datetime": "2025-01-02", "horizon": "1", "y_true": "1", "y_pred": "1"},
            {"ticker": "VCB", "datetime": "2025-01-03", "horizon": "1", "y_true": "0", "y_pred": "1"},
        ),
        default_timeframe="1d",
    )

    evaluation = evaluate_forecast_vs_actual(converted)

    assert evaluation["actual_data_status"] == "provided"
    assert evaluation["rows_total"] == 2
    assert evaluation["directional_accuracy"] == 0.5


def test_ambiguous_direction_rejects_clearly():
    with pytest.raises(ValueError, match="unsupported prediction direction"):
        convert_legacy_rows_to_forecast_actual(
            ({"ticker": "VCB", "datetime": "2025-01-02", "horizon": "1", "y_true": "1", "y_pred": "maybe"},),
            default_timeframe="1d",
        )
