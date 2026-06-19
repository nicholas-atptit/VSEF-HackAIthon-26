from src.hackaithon_mvp.diagnostic_chain.calibration_engine import run_calibration


def test_calibration_does_not_fine_tune():
    output = run_calibration(
        {"consensus_strength": 0.2},
        {"scenario_confidence": 0.5},
        {"risk_level": "medium"},
        {"decision_lane": "watchlist_review"},
    )
    assert output["fine_tuning_performed"] is False
    assert output["calibration_policy"] == "static_confidence_adjustment_only"
    assert 0.0 <= output["calibrated_confidence"] <= 1.0
