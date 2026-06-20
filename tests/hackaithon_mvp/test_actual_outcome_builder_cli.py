import json
import subprocess
import sys


def _write_fixture_files(tmp_path):
    forecasts = [
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "prediction_timestamp": "2026-01-01T00:00:00+07:00",
            "horizon_steps": 1,
            "forecast_diagnostic": "positive_bias",
            "model_family": "classification",
        }
    ]
    bars = [
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "timestamp": "2026-01-01T00:00:00+07:00",
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10,
            "volume": 100,
        },
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "timestamp": "2026-01-02T00:00:00+07:00",
            "open": 12,
            "high": 13,
            "low": 11,
            "close": 12,
            "volume": 100,
        },
    ]
    forecast_path = tmp_path / "forecasts.jsonl"
    bar_path = tmp_path / "bars.jsonl"
    forecast_path.write_text("\n".join(json.dumps(row) for row in forecasts) + "\n", encoding="utf-8")
    bar_path.write_text("\n".join(json.dumps(row) for row in bars) + "\n", encoding="utf-8")
    return forecast_path, bar_path


def _run(*args):
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.actual_outcome_builder", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_cli_exits_cleanly_with_tiny_local_fixture(tmp_path):
    forecast_path, bar_path = _write_fixture_files(tmp_path)
    output = _run("--forecasts", str(forecast_path), "--bars", str(bar_path), "--format", "json")

    assert output["actual_outcome_summary"]["rows_total"] == 1
    assert output["actual_outcome_summary"]["actual_direction_label_counts"] == {"positive": 1}


def test_cli_evaluate_returns_evaluation_summary(tmp_path):
    forecast_path, bar_path = _write_fixture_files(tmp_path)
    output = _run("--forecasts", str(forecast_path), "--bars", str(bar_path), "--evaluate")

    assert output["evaluation"]["actual_data_status"] == "provided"
    assert output["evaluation"]["rows_total"] == 1
    assert output["evaluation"]["directional_accuracy"] == 1


def test_cli_writes_only_when_requested(tmp_path):
    forecast_path, bar_path = _write_fixture_files(tmp_path)
    output_path = tmp_path / "actual_rows.jsonl"
    output = _run(
        "--forecasts",
        str(forecast_path),
        "--bars",
        str(bar_path),
        "--format",
        "jsonl",
        "--write",
        str(output_path),
    )

    assert output["actual_outcome_summary"]["written_path"] == str(output_path)
    assert output_path.exists()
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 1
