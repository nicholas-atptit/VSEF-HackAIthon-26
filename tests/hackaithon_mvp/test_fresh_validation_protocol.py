from datetime import date, timedelta

import pytest

from src.hackaithon_mvp.fresh_validation_protocol import (
    build_nested_walk_forward_protocol,
    build_three_way_time_split,
    render_fresh_validation_protocol_report,
)


def _rows(count=30):
    start = date(2025, 1, 1)
    rows = []
    for index in range(count):
        forecast_day = start + timedelta(days=index)
        actual_day = forecast_day + timedelta(days=1)
        rows.append(
            {
                "ticker": "AAA",
                "model_id": "m1",
                "horizon": 1,
                "forecast_timestamp": forecast_day.isoformat(),
                "actual_timestamp": actual_day.isoformat(),
                "predicted_direction": "up" if index % 2 == 0 else "down",
                "actual_direction": "up" if index % 2 == 0 else "down",
            }
        )
    return rows


def test_three_way_time_split_is_grouped_and_post_hoc():
    result = build_three_way_time_split(_rows())
    report = render_fresh_validation_protocol_report(result)

    assert result["split_status"] == "ready"
    assert result["train_row_count"] == 18
    assert result["validation_row_count"] == 6
    assert result["holdout_row_count"] == 6
    assert result["validation_protocol_status"] == "post_hoc_repair_validation"
    assert result["truly_fresh_holdout_exists"] is False
    assert "Fresh Validation Protocol" in report


def test_three_way_split_rejects_invalid_fractions():
    with pytest.raises(ValueError):
        build_three_way_time_split(_rows(), train_fraction=0.5, validation_fraction=0.2, holdout_fraction=0.2)


def test_nested_walk_forward_protocol_reports_ready_folds():
    result = build_nested_walk_forward_protocol(_rows(120))

    assert result["protocol_status"] == "ready"
    assert result["ready_fold_count"] >= 1
    assert result["previous_holdout_already_inspected"] is True
