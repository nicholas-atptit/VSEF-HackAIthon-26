from src.hackaithon_mvp.model_champion_selector import (
    render_model_champion_report,
    select_champions_by_slice,
)


def _candidate(model_id, horizon, bacc, *, majority=0.52, previous=0.8, rows=100):
    return {
        "model_id": model_id,
        "ticker": "AAA",
        "horizon": horizon,
        "post_tune_validation_metrics": {
            "balanced_accuracy": bacc,
            "accuracy": bacc,
            "mcc": bacc - 0.5,
            "coverage_count": rows,
        },
        "validation_rows": rows,
        "baseline_comparison": {
            "majority_class_baseline_accuracy": majority,
            "random_50_50_baseline_accuracy": 0.5,
            "previous_direction_baseline_accuracy": previous,
        },
    }


def test_selects_best_candidate_that_beats_random():
    result = select_champions_by_slice(
        [
            _candidate("weak", 5, 0.49),
            _candidate("strong", 5, 0.56, previous=0.54),
        ]
    )

    assert result["selection_status"] == "completed"
    assert result["global_champion"]["model_id"] == "strong"
    assert result["beats_random_count"] == 1
    assert result["beats_majority_count"] == 1
    assert result["beats_previous_direction_count"] == 1


def test_marks_previous_direction_dominance_as_diagnostic_only():
    result = select_champions_by_slice([_candidate("okay", 10, 0.56, previous=0.95)])

    assert result["global_champion"]["champion_status"] == "diagnostic_only_not_superior"
    assert result["beats_previous_direction_count"] == 0


def test_champion_report_is_bounded():
    report = render_model_champion_report(select_champions_by_slice([_candidate("okay", 10, 0.56)])).lower()

    assert "model champion selection" in report
    for forbidden in ("buy", "sell", "hold"):
        assert forbidden not in report
