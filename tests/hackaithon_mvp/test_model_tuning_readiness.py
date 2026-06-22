import json
import subprocess
import sys
from datetime import datetime, timedelta

from src.hackaithon_mvp.model_tuning_readiness import (
    inspect_local_tuning_inputs,
    render_model_tuning_readiness_report,
    run_model_tuning_readiness_gate,
)


def _row(index: int, *, ticker: str = "AAA", horizon: int = 5, diagnostic: str = "positive_bias", actual: str = "positive") -> dict:
    timestamp = datetime(2026, 1, 1) + timedelta(days=index)
    return {
        "ticker": ticker,
        "timeframe": "1d",
        "prediction_timestamp": timestamp.strftime("%Y-%m-%dT00:00:00+07:00"),
        "horizon_steps": horizon,
        "forecast_diagnostic": diagnostic,
        "actual_future_return": 0.01 if actual == "positive" else -0.01,
        "actual_direction_label": actual,
        "model_family": "classification",
        "diagnostic_score": 0.55 + index / 1000,
        "confidence": 0.6,
    }


def test_model_tuning_readiness_reports_no_labeled_data_for_empty_root(tmp_path):
    result = run_model_tuning_readiness_gate(search_roots=(str(tmp_path),))

    assert result["readiness_status"] == "not_ready_no_labeled_data"
    assert "local_labeled_forecast_actual_rows_missing" in result["blocking_reasons"]
    assert result["claim_boundary"]["no_training"] is True


def test_model_tuning_readiness_detects_limited_policy_search_fixture(tmp_path):
    path = tmp_path / "forecast_actual.jsonl"
    rows = [_row(index, actual="positive" if index % 2 == 0 else "negative") for index in range(12)]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    result = run_model_tuning_readiness_gate(search_roots=(str(tmp_path),))

    assert result["readiness_status"] == "ready_for_limited_policy_search_only"
    assert result["checks"]["temporal_split_possible"] is True
    assert result["inspection"]["labeled_artifact_count"] == 1


def test_model_tuning_readiness_detects_local_diagnostic_tuning_fixture(tmp_path):
    path = tmp_path / "forecast_actual.jsonl"
    rows = [
        _row(index, ticker="AAA" if index < 40 else "BBB", actual="positive" if index % 2 == 0 else "negative")
        for index in range(80)
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    result = run_model_tuning_readiness_gate(search_roots=(str(tmp_path),))

    assert result["readiness_status"] == "ready_for_local_diagnostic_tuning"
    assert result["inspection"]["total_labeled_rows"] == 80


def test_model_tuning_readiness_inspection_ignores_invalid_artifact(tmp_path):
    (tmp_path / "forecast_actual_bad.json").write_text('{"rows": [{"not": "forecast"}]}', encoding="utf-8")

    result = inspect_local_tuning_inputs(search_roots=(str(tmp_path),))

    assert result["candidate_file_count"] == 1
    assert result["labeled_artifact_count"] == 0


def test_model_tuning_readiness_report_and_cli(tmp_path):
    result = run_model_tuning_readiness_gate(search_roots=(str(tmp_path),))
    report = render_model_tuning_readiness_report(result)

    assert "Model Tuning Readiness" in report
    assert "Readiness status: not_ready_no_labeled_data" in report

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.model_tuning_readiness",
            "--search-root",
            str(tmp_path),
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Readiness status: not_ready_no_labeled_data" in completed.stdout
