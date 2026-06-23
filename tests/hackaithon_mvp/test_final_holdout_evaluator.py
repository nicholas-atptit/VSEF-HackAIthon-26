from src.hackaithon_mvp.final_holdout_evaluator import (
    build_final_holdout_split,
    evaluate_final_holdout,
    render_final_holdout_report,
)


def _rows(count=30):
    rows = []
    for index in range(count):
        actual = "up" if index % 2 == 0 else "down"
        rows.append(
            {
                "ticker": "AAA",
                "horizon": 20,
                "model_id": "m1",
                "forecast_timestamp": f"2025-03-{index + 1:02d}",
                "predicted_direction": actual,
                "predicted_probability": 0.7 if actual == "up" else 0.3,
                "actual_direction": actual,
            }
        )
    return rows


def test_build_final_holdout_split_uses_latest_rows():
    result = build_final_holdout_split(_rows(20), holdout_fraction=0.2)

    assert result["split_status"] == "ready"
    assert result["holdout_row_count"] == 4
    assert result["holdout_rows"][0]["forecast_timestamp"] == "2025-03-17"


def test_evaluate_final_holdout_scores_fixed_policy():
    result = evaluate_final_holdout(_rows(30), {"policy_id": "fixed", "confidence_threshold": 0.6})
    report = render_final_holdout_report(result)

    assert result["holdout_status"] == "evaluated"
    assert result["global_balanced_accuracy"] == 1.0
    assert result["coverage"] == 1.0
    assert result["beats_random"] is True
    assert "Final Holdout" in report


def test_evaluate_final_holdout_can_use_input_as_holdout_rows():
    result = evaluate_final_holdout(_rows(10), {"policy_id": "fixed", "rows_are_holdout": True})

    assert result["holdout_rows"] == 10
    assert result["scored_holdout_rows"] == 10
