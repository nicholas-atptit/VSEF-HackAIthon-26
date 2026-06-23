from src.hackaithon_mvp.forecast_data_repair_audit import (
    audit_forecast_dataset_integrity,
    identify_duplicate_prediction_keys,
    identify_overlapping_label_windows,
    identify_unstable_slices,
    render_forecast_data_repair_report,
)


def _rows():
    rows = []
    for index in range(8):
        actual = "up" if index < 6 else "down"
        rows.append(
            {
                "ticker": "AAA",
                "model_id": "m1",
                "horizon": 5,
                "forecast_timestamp": f"2025-01-{index + 1:02d}",
                "actual_timestamp": f"2025-01-{index + 6:02d}",
                "predicted_direction": actual,
                "actual_direction": actual,
                "actual_return": 0.01 if actual == "up" else -0.01,
                "deoverlap_step_index": index,
            }
        )
    duplicate = dict(rows[-1])
    duplicate["actual_direction"] = "up"
    rows.append(duplicate)
    rows.append(
        {
            "ticker": "AAA",
            "model_id": "m1",
            "horizon": 5,
            "forecast_timestamp": "2025-02-01",
            "actual_timestamp": "2025-01-31",
            "predicted_direction": "up",
            "actual_direction": "down",
        }
    )
    return rows


def test_duplicate_prediction_keys_are_counted():
    result = identify_duplicate_prediction_keys(_rows())

    assert result["duplicate_key_count"] == 1
    assert result["duplicate_row_count"] == 1
    assert result["duplicate_key_severity"] in {"low", "medium", "high"}


def test_overlapping_windows_and_unstable_slices_are_reported():
    overlap = identify_overlapping_label_windows(_rows())
    unstable = identify_unstable_slices(_rows())

    assert overlap["overlap_row_count"] > 0
    assert overlap["overlap_warning"] is True
    assert unstable["unstable_slice_count"] >= 1


def test_full_repair_audit_reports_timestamp_and_leakage_risk():
    result = audit_forecast_dataset_integrity(_rows())
    report = render_forecast_data_repair_report(result).lower()

    assert result["timestamp_order"]["rows_where_forecast_timestamp_ge_actual_timestamp"] == 1
    assert result["leakage_warning"] is True
    assert result["recommended_repair_actions"]
    assert "forecast data repair audit" in report
    for forbidden in ("buy", "sell", "hold"):
        assert forbidden not in report
