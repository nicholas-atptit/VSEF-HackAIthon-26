from src.hackaithon_mvp.release_baseline_sanity_audit import (
    audit_previous_direction_baseline,
    audit_release_baselines,
    render_release_baseline_sanity_report,
)


def _persistent_rows(count=20):
    rows = []
    for index in range(count):
        rows.append(
            {
                "ticker": "AAA",
                "model_id": "model-a",
                "horizon": 40,
                "forecast_timestamp": f"2025-01-{index + 1:02d}",
                "actual_direction": "up",
                "predicted_direction": "up",
            }
        )
    return rows


def test_previous_direction_baseline_detects_high_persistence_and_overlap():
    result = audit_previous_direction_baseline(_persistent_rows())

    assert result["previous_direction_sample_count"] == 19
    assert result["previous_direction_accuracy"] == 1.0
    assert result["warning_high_persistence"] is True
    assert result["overlap_warning"] is True
    assert result["leakage_warning"] is False


def test_duplicate_timestamp_collision_is_reported():
    rows = _persistent_rows(3)
    rows.append(dict(rows[-1]))

    result = audit_previous_direction_baseline(rows)

    assert result["duplicate_key_count"] == 1
    assert result["duplicate_row_count"] == 1


def test_release_baseline_report_is_bounded():
    result = audit_release_baselines(_persistent_rows())
    report = render_release_baseline_sanity_report(result).lower()

    assert "release baseline sanity audit" in report
    assert "high persistence warning: true" in report
    for forbidden in ("buy", "sell", "hold"):
        assert forbidden not in report
