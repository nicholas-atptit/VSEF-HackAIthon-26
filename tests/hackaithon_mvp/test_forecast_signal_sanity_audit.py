from src.hackaithon_mvp.forecast_signal_sanity_audit import (
    audit_label_polarity,
    audit_prediction_flip_rescue,
    audit_probability_polarity,
    render_forecast_signal_sanity_report,
    run_forecast_signal_sanity_audit,
)


def _inverse_rows():
    rows = []
    for index in range(20):
        actual = "up" if index % 2 == 0 else "down"
        predicted = "down" if actual == "up" else "up"
        rows.append(
            {
                "ticker": "AAA",
                "model_id": "model-a",
                "horizon": 5,
                "forecast_timestamp": f"2025-01-{index + 1:02d}",
                "actual_direction": actual,
                "predicted_direction": predicted,
                "predicted_probability": 0.8 if predicted == "up" else 0.2,
            }
        )
    return rows


def test_label_and_probability_audits_summarize_mapping():
    labels = audit_label_polarity(_inverse_rows())
    probability = audit_probability_polarity(_inverse_rows())

    assert labels["actual_label_values"]["up"] == 10
    assert labels["predicted_label_values"]["down"] == 10
    assert probability["possible_probability_polarity_mismatch"] is False


def test_flip_rescue_flags_possible_label_polarity_mismatch():
    result = audit_prediction_flip_rescue(_inverse_rows())

    assert result["original_metrics"]["balanced_accuracy"] == 0.0
    assert result["flipped_metrics"]["balanced_accuracy"] == 1.0
    assert result["possible_label_polarity_mismatch"] is True
    assert result["flipped_predictions_materially_outperform_original"] is True


def test_signal_sanity_report_renders_without_action_labels():
    result = run_forecast_signal_sanity_audit(_inverse_rows())
    report = render_forecast_signal_sanity_report(result).lower()

    assert "forecast signal sanity audit" in report
    assert "possible label polarity mismatch: true" in report
    for forbidden in ("buy", "sell", "hold"):
        assert forbidden not in report
