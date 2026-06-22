import csv
import json

from src.hackaithon_mvp.forecast_actual_artifact_discovery import (
    discover_forecast_actual_artifacts,
    render_forecast_actual_artifact_report,
)


def test_discovery_finds_usable_forecast_actual_csv(tmp_path):
    path = tmp_path / "forecast_actual_rows.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "symbol",
                "model_id",
                "horizon",
                "forecast_timestamp",
                "predicted_direction",
                "actual_direction",
                "predicted_probability",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "symbol": "AAA",
                "model_id": "m1",
                "horizon": 1,
                "forecast_timestamp": "2026-01-01",
                "predicted_direction": "up",
                "actual_direction": "up",
                "predicted_probability": 0.6,
            }
        )

    result = discover_forecast_actual_artifacts(repo_root=str(tmp_path))

    assert result["candidate_file_count"] == 1
    assert result["usable_accuracy_file_count"] == 1
    assert result["usable_tuning_file_count"] == 1
    assert result["candidate_files"][0]["missing_columns"] == []


def test_discovery_classifies_bar_data_as_not_accuracy_ready(tmp_path):
    path = tmp_path / "local_bars_ohlcv.jsonl"
    path.write_text(
        json.dumps({"symbol": "AAA", "date": "2026-01-01", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10})
        + "\n",
        encoding="utf-8",
    )

    result = discover_forecast_actual_artifacts(repo_root=str(tmp_path))

    assert result["candidate_file_count"] == 1
    assert result["candidate_files"][0]["usable_for_accuracy"] is False
    assert "bar_data_only_not_forecast_actual" in result["candidate_files"][0]["risk_notes"]


def test_discovery_ignores_tmp_and_renders_report(tmp_path):
    ignored = tmp_path / ".tmp_outputs"
    ignored.mkdir()
    (ignored / "forecast_actual_rows.json").write_text("[]", encoding="utf-8")

    result = discover_forecast_actual_artifacts(repo_root=str(tmp_path))
    report = render_forecast_actual_artifact_report(result)

    assert result["candidate_file_count"] == 0
    assert "Forecast-vs-Actual Artifact Discovery" in report
    assert "write files" in report
