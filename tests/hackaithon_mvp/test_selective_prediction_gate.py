from src.hackaithon_mvp.selective_prediction_gate import (
    evaluate_confidence_buckets,
    render_selective_prediction_report,
    tune_confidence_gate,
)


def _rows():
    rows = []
    for index in range(20):
        actual = "up" if index % 2 == 0 else "down"
        probability = 0.8 if actual == "up" else 0.2
        if index % 5 == 0:
            probability = 0.51
        rows.append(
            {
                "ticker": "AAA",
                "horizon": 20,
                "model_id": "m1",
                "forecast_timestamp": f"2025-01-{index + 1:02d}",
                "predicted_probability": probability,
                "predicted_direction": "up" if probability >= 0.5 else "down",
                "actual_direction": actual,
            }
        )
    return rows


def test_confidence_buckets_report_retained_and_abstained_rows():
    result = evaluate_confidence_buckets(_rows())

    assert result["evaluation_status"] == "completed"
    assert result["probability_rows"] == 20
    assert result["threshold_results"][0]["rows_retained"] == 20
    assert result["threshold_results"][-1]["rows_abstained"] > 0
    assert result["row_labels"]["abstained"] == "abstained_low_confidence"


def test_tune_confidence_gate_selects_threshold_with_minimum_coverage():
    result = tune_confidence_gate(_rows())
    report = render_selective_prediction_report(result)

    assert result["tuning_status"] == "completed"
    assert result["selected_threshold"] is not None
    assert result["selected_metrics"]["coverage"] >= 0.3
    assert "Select" in report
