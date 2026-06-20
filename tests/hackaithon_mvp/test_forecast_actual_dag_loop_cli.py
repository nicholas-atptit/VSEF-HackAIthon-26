import json
import subprocess
import sys
from pathlib import Path


def _write_jsonl(path: Path, rows: tuple[dict, ...]) -> Path:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    return path


def _forecast_rows():
    return (
        {
            "ticker": "VCB",
            "timeframe": "1d",
            "prediction_timestamp": "2026-01-01T00:00:00+07:00",
            "horizon_steps": 1,
            "forecast_diagnostic": "positive_bias",
            "diagnostic_score": 0.9,
        },
    )


def _bar_rows():
    return (
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
    )


def test_cli_exits_cleanly_with_tiny_local_fixtures(tmp_path):
    forecasts = _write_jsonl(tmp_path / "forecasts.jsonl", _forecast_rows())
    bars = _write_jsonl(tmp_path / "bars.jsonl", _bar_rows())

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.forecast_actual_dag_loop",
            "--forecasts",
            str(forecasts),
            "--bars",
            str(bars),
            "--top-k",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["loop_status"] == "completed"
    assert payload["actual_outcome_rows"] == 1
    assert payload["storage_write_enabled"] is False


def test_cli_persist_writes_only_under_temp_root(tmp_path):
    forecasts = _write_jsonl(tmp_path / "forecasts.jsonl", _forecast_rows())
    bars = _write_jsonl(tmp_path / "bars.jsonl", _bar_rows())
    storage_root = tmp_path / "storage"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.forecast_actual_dag_loop",
            "--forecasts",
            str(forecasts),
            "--bars",
            str(bars),
            "--storage-root",
            str(storage_root),
            "--ticker",
            "VCB",
            "--timeframe",
            "1d",
            "--date",
            "2026-01-01",
            "--persist",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["storage_write_enabled"] is True
    assert payload["storage_write_summary"]["records_written"] == 2
    for write_result in payload["storage_write_summary"]["write_results"].values():
        assert write_result["actual_path"].startswith(str(storage_root).replace("\\", "/"))
