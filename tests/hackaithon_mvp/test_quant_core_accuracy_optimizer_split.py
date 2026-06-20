from src.hackaithon_mvp.quant_core_accuracy_optimizer import split_rows_for_policy_validation


def _row(index, timestamp):
    return {
        "ticker": "AAA",
        "timeframe": "1h",
        "prediction_timestamp": timestamp,
        "horizon_steps": 40,
        "forecast_diagnostic": "positive_bias",
        "actual_future_return": 1.0,
        "actual_direction_label": "positive",
    }


def test_chronological_split_sorts_by_timestamp():
    rows = (
        _row(0, "2026-01-03T00:00:00"),
        _row(1, "2026-01-01T00:00:00"),
        _row(2, "2026-01-02T00:00:00"),
    )

    split = split_rows_for_policy_validation(rows, calibration_ratio=2 / 3)

    assert split["split_method"] == "chronological_prediction_timestamp"
    assert [row["prediction_timestamp"] for row in split["calibration_rows"]] == [
        "2026-01-01T00:00:00",
        "2026-01-02T00:00:00",
    ]
    assert split["validation_rows"][0]["prediction_timestamp"] == "2026-01-03T00:00:00"


def test_synthetic_row_index_split_preserves_order():
    rows = tuple(_row(index, f"row_index_{index}") for index in range(5))

    split = split_rows_for_policy_validation(rows, calibration_ratio=0.6)

    assert split["split_method"] == "synthetic_row_index_order"
    assert [row["prediction_timestamp"] for row in split["calibration_rows"]] == [
        "row_index_0",
        "row_index_1",
        "row_index_2",
    ]
