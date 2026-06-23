from src.hackaithon_mvp.diagnostic_ensemble_selector import (
    build_simple_ensembles,
    evaluate_ensemble_candidates,
    render_diagnostic_ensemble_report,
)


def _rows():
    rows = []
    for index in range(12):
        actual = "up" if index % 2 == 0 else "down"
        timestamp = f"2025-02-{index + 1:02d}"
        rows.extend(
            [
                {
                    "ticker": "AAA",
                    "horizon": 20,
                    "model_id": "good",
                    "forecast_timestamp": timestamp,
                    "predicted_direction": actual,
                    "predicted_probability": 0.8 if actual == "up" else 0.2,
                    "actual_direction": actual,
                },
                {
                    "ticker": "AAA",
                    "horizon": 20,
                    "model_id": "weak",
                    "forecast_timestamp": timestamp,
                    "predicted_direction": "down" if actual == "up" else "up",
                    "predicted_probability": 0.4 if actual == "up" else 0.6,
                    "actual_direction": actual,
                },
            ]
        )
    return rows


def test_build_simple_ensembles_creates_method_rows():
    result = build_simple_ensembles(_rows())

    assert result["ensemble_status"] == "completed"
    assert result["row_counts_by_method"]["majority_vote"] > 0
    assert result["row_counts_by_method"]["probability_average"] > 0


def test_evaluate_ensemble_candidates_selects_a_method():
    result = evaluate_ensemble_candidates(_rows())
    report = render_diagnostic_ensemble_report(result)

    assert result["ensemble_evaluation_status"] == "completed"
    assert result["selected_method"] in result["evaluations"]
    assert "Diagnostic Ensemble" in report
