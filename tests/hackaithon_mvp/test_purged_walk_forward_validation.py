from src.hackaithon_mvp.purged_walk_forward_validation import (
    purged_temporal_split,
    render_purged_walk_forward_report,
    run_walk_forward_folds,
)


def _rows(count=40, horizon=5):
    return [
        {
            "ticker": "AAA",
            "horizon": horizon,
            "timestamp": f"2025-01-{index + 1:02d}",
            "forecast_timestamp": f"2025-01-{index + 1:02d}",
            "actual_direction": "up" if index % 2 == 0 else "down",
            "predicted_direction": "up" if index % 3 == 0 else "down",
        }
        for index in range(count)
    ]


def test_purged_split_removes_overlap_and_embargo_rows():
    split = purged_temporal_split(_rows(), horizon_steps=5, validation_fraction=0.25, embargo_steps=2)

    assert split["split_status"] == "ready"
    assert split["validation_row_count"] == 10
    assert split["purged_row_count"] > 0
    assert split["train_row_count"] < 30


def test_walk_forward_folds_report_metrics():
    result = run_walk_forward_folds(_rows(), n_folds=2, horizon_steps=5)
    report = render_purged_walk_forward_report(result)

    assert result["walk_forward_status"] == "completed"
    assert result["ready_fold_count"] == 2
    assert "Purged Walk-forward Validation" in report
