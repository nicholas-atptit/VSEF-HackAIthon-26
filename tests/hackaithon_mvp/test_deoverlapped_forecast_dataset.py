from src.hackaithon_mvp.deoverlapped_forecast_dataset import (
    build_deoverlapped_forecast_dataset,
    build_non_overlapping_rows,
    remove_duplicate_prediction_keys,
    render_deoverlapped_dataset_report,
)


def _rows():
    rows = []
    for index in range(12):
        rows.append(
            {
                "ticker": "AAA",
                "model_id": "m1",
                "horizon": 5,
                "forecast_timestamp": f"2025-01-{index + 1:02d}",
                "actual_timestamp": f"2025-01-{index + 6:02d}",
                "predicted_direction": "up" if index % 2 == 0 else "down",
                "actual_direction": "up" if index % 2 == 0 else "down",
                "actual_return": 0.01 if index % 2 == 0 else -0.01,
                "deoverlap_step_index": index,
            }
        )
    duplicate = dict(rows[5])
    duplicate["predicted_probability"] = 0.9
    rows.append(duplicate)
    return rows


def test_remove_duplicate_prediction_keys_keeps_one_row_per_key():
    result = remove_duplicate_prediction_keys(_rows())

    assert result["deduplication_status"] == "completed"
    assert result["dropped_duplicate_rows"] == 1
    assert result["duplicate_key_count"] == 1
    assert result["retained_rows"] == 12


def test_build_non_overlapping_rows_respects_horizon_steps():
    result = build_non_overlapping_rows(_rows()[:12], horizon_steps=5)

    assert result["deoverlap_status"] == "completed"
    assert result["retained_rows"] == 3
    assert result["dropped_overlap_rows"] == 9


def test_build_deoverlapped_forecast_dataset_reports_drops():
    result = build_deoverlapped_forecast_dataset(_rows())
    report = render_deoverlapped_dataset_report({key: value for key, value in result.items() if key != "rows"})

    assert result["input_rows"] == 13
    assert result["dropped_duplicate_rows"] == 1
    assert result["dropped_overlap_rows"] == 9
    assert result["retained_rows"] == 3
    assert "De-overlapped Forecast Dataset" in report
