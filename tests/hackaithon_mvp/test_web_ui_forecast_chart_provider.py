import json
from pathlib import Path

from src.hackaithon_mvp.web_ui.forecast_chart_provider import (
    build_forecast_accuracy_timeline,
    build_forecast_chart_data,
    build_horizon_comparison_chart,
    discover_forecast_chart_artifacts,
    validate_forecast_chart_payload,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_artifact_discovery_uses_only_safe_local_paths(tmp_path):
    discovery = discover_forecast_chart_artifacts(repo_root=str(tmp_path))

    assert discovery["safe_roots_only"] is True
    assert discovery["local_only"] is True
    assert discovery["provider_calls"] is False
    assert discovery["writes_files"] is False
    assert all(".." not in path for path in discovery["searched_paths"])
    assert ".tmp_forecast_edge/retained_forecast_rows.jsonl" in discovery["searched_paths"]
    assert ".tmp_forecast_repair/forecast_actual_rows.jsonl" in discovery["searched_paths"]


def test_chart_payload_unavailable_when_row_evidence_missing(tmp_path):
    payload = build_forecast_chart_data("VCB", horizon="h1", repo_root=str(tmp_path))

    assert payload["available"] is False
    assert payload["reason"] == "row_level_forecast_evidence_missing"
    assert payload["points"] == []
    assert validate_forecast_chart_payload(payload)["valid"] is True


def test_chart_payload_validates_with_minimal_row_evidence(tmp_path):
    _write_jsonl(
        tmp_path / ".tmp_forecast_edge" / "retained_forecast_rows.jsonl",
        [
            {
                "ticker": "VCB",
                "forecast_timestamp": "2026-01-02T10:00:00",
                "horizon": 1,
                "actual_close": 92100,
                "predicted_direction": "up",
                "actual_direction": "up",
                "predicted_probability": 0.64,
            },
            {
                "ticker": "VCB",
                "forecast_timestamp": "2026-01-03T10:00:00",
                "horizon": 1,
                "actual_close": 91800,
                "predicted_direction": "down",
                "actual_direction": "up",
                "predicted_probability": 0.41,
            },
        ],
    )

    chart = build_forecast_chart_data("VCB", horizon="h1", repo_root=str(tmp_path))
    timeline = build_forecast_accuracy_timeline("VCB", horizon="h1", repo_root=str(tmp_path))
    comparison = build_horizon_comparison_chart("VCB", repo_root=str(tmp_path))

    assert chart["available"] is True
    assert chart["source_artifact"] == ".tmp_forecast_edge/retained_forecast_rows.jsonl"
    assert chart["metrics"]["rows"] == 2
    assert chart["metrics"]["accuracy"] == 0.5
    assert chart["points"][0]["actual_close"] == 92100
    assert chart["points"][0]["correct"] is True
    assert validate_forecast_chart_payload(chart)["valid"] is True
    assert timeline["available"] is True
    assert timeline["timeline"][-1]["cumulative_accuracy"] == 0.5
    assert comparison["available"] is True
    assert "h1" in comparison["available_horizons"]
