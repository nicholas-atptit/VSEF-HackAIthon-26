from src.hackaithon_mvp.quant_core_calibration import (
    build_confidence_calibration_report,
    build_score_calibration_report,
)


def _row(score, diagnostic, actual, index):
    return {
        "ticker": "AAA",
        "timeframe": "1h",
        "prediction_timestamp": f"2026-01-01T{index:02d}:00:00",
        "horizon_steps": 40,
        "forecast_diagnostic": diagnostic,
        "actual_future_return": 1.0 if actual == "positive" else -1.0,
        "actual_direction_label": actual,
        "diagnostic_score": score,
        "confidence": score,
    }


def test_calibration_report_detects_score_inversion():
    rows = []
    for index in range(10):
        rows.append(_row(index / 100, "positive_bias", "positive", index))
    for index in range(10, 20):
        rows.append(_row(0.9 + index / 1000, "positive_bias", "negative", index))

    report = build_score_calibration_report(tuple(rows), bins=2)

    assert report["eligible_rows"] == 20
    assert report["bottom_bin_accuracy"] == 1.0
    assert report["top_bin_accuracy"] == 0.0
    assert report["inversion_suspected"] is True
    assert report["ranking_warning"] == "score_may_be_inverted_or_not_calibrated"


def test_calibration_report_handles_missing_score_field_safely():
    rows = (
        {
            "ticker": "AAA",
            "timeframe": "1h",
            "prediction_timestamp": "2026-01-01T00:00:00",
            "horizon_steps": 40,
            "forecast_diagnostic": "positive_bias",
            "actual_future_return": 1.0,
            "actual_direction_label": "positive",
        },
    )

    report = build_score_calibration_report(rows, bins=3)

    assert report["rows_total"] == 1
    assert report["eligible_rows"] == 0
    assert report["bins"] == []
    assert report["ranking_warning"] == "score_field_missing_or_unusable"


def test_confidence_calibration_uses_confidence_field():
    rows = (
        _row(0.1, "positive_bias", "positive", 1),
        _row(0.9, "positive_bias", "positive", 2),
    )

    report = build_confidence_calibration_report(rows, bins=2)

    assert report["field"] == "confidence"
    assert report["eligible_rows"] == 2
    assert report["inversion_suspected"] is False


def test_calibration_report_warns_when_top_scored_slice_underperforms_global():
    rows = []
    for index in range(100):
        rows.append(_row(index / 1000, "positive_bias", "positive", index))
    for index in range(100, 150):
        rows.append(_row(0.9 + index / 1000, "positive_bias", "negative", index))

    report = build_score_calibration_report(tuple(rows), bins=10)

    assert report["global_accuracy"] == round(100 / 150, 6)
    assert report["top_slice_accuracy"] == 0.0
    assert report["top_slice_warning"] == "top_scored_slice_underperformed_global"
    assert report["ranking_warning"] in {
        "score_may_be_inverted_or_not_calibrated",
        "score_not_calibrated_for_top_slice_selection",
    }
