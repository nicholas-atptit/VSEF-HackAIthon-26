import json
import re
from datetime import datetime, timedelta

from src.hackaithon_mvp.eligible_model_policy_tuner import tune_all_eligible_models
from src.hackaithon_mvp.release_accuracy_report import (
    build_release_accuracy_report,
    render_release_accuracy_report,
)


def _rows(count=12):
    rows = []
    start = datetime(2026, 1, 1, 9, 0, 0)
    for index in range(count):
        actual_up = index % 2 == 0
        timestamp = start + timedelta(days=index)
        rows.append(
            {
                "ticker": "AAA" if index % 3 else "BBB",
                "model_id": "model-a",
                "model_family": "classification",
                "horizon": 1,
                "forecast_timestamp": timestamp.isoformat(),
                "predicted_direction": "up" if actual_up else "down",
                "actual_direction": "up" if actual_up else "down",
                "predicted_probability": 0.56 if actual_up else 0.44,
                "predicted_return": 0.01 if actual_up else -0.01,
                "actual_return": 0.02 if actual_up else -0.02,
            }
        )
    return rows


def _write_rows(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_release_report_without_input_does_not_claim_accuracy():
    result = build_release_accuracy_report()

    assert result["release_accuracy_status"] == "not_ready_no_forecast_actual_rows"
    assert result["evaluated_row_count"] == 0
    assert "explicit_input_required_for_accuracy" in result["limitations"]


def test_release_report_with_small_input_allows_demo_accuracy_disclosure(tmp_path):
    input_path = tmp_path / "forecast_actual_rows.jsonl"
    _write_rows(input_path, _rows(12))

    result = build_release_accuracy_report(input_path=str(input_path))

    assert result["release_accuracy_status"] == "ready_for_demo_accuracy_disclosure"
    assert result["evaluated_row_count"] == 12
    assert result["global_directional_accuracy"] == 1.0
    assert result["baseline_comparison"]["majority_class_baseline_accuracy"] is not None
    assert result["by_ticker"]
    assert result["by_horizon"]
    assert result["by_model"]
    assert result["forecast_release_status"] == "forecast_release_blocked_insufficient_rows"


def test_release_report_marks_larger_threshold_ready_input_as_tuning_required(tmp_path):
    input_path = tmp_path / "forecast_actual_rows.jsonl"
    _write_rows(input_path, _rows(36))

    result = build_release_accuracy_report(input_path=str(input_path))

    assert result["release_accuracy_status"] == "not_ready_tuning_required"
    assert result["tuning_readiness"]["tuning_gate_status"] == "ready_for_policy_threshold_tuning"


def test_release_report_includes_tuning_output_when_provided(tmp_path):
    input_path = tmp_path / "forecast_actual_rows.jsonl"
    tuning_path = tmp_path / ".tmp_tuning_report.json"
    rows = _rows(36)
    _write_rows(input_path, rows)
    tuning_path.write_text(json.dumps(tune_all_eligible_models(rows)), encoding="utf-8")

    result = build_release_accuracy_report(input_path=str(input_path), tuning_output_path=str(tuning_path))

    assert result["release_accuracy_status"] == "release_ready_with_local_accuracy"
    assert result["tuning_result"]["tuning_status"] == "completed"
    assert result["forecast_release_status"] == "forecast_release_blocked_insufficient_rows"


def test_release_report_discover_mode_is_dry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = build_release_accuracy_report(discover=True)

    assert result["artifact_discovery"]["discovery_status"] == "completed"
    assert result["release_accuracy_status"] == "not_ready_no_forecast_actual_rows"


def test_release_report_render_has_no_market_action_labels(tmp_path):
    input_path = tmp_path / "forecast_actual_rows.jsonl"
    _write_rows(input_path, _rows(12))

    report = render_release_accuracy_report(build_release_accuracy_report(input_path=str(input_path))).lower()

    assert "Release Accuracy Report" in render_release_accuracy_report(build_release_accuracy_report(input_path=str(input_path)))
    assert "60 percent forecast release status" in report
    for forbidden in ("buy", "sell", "hold"):
        assert re.search(rf"\b{forbidden}\b", report) is None
