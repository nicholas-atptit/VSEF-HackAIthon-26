import json
import subprocess
import sys
from pathlib import Path

from src.hackaithon_mvp.local_storage.parquet_adapter import write_dataset_records


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.diagnostic_dag.dag_cli", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_cli_default_does_not_write(tmp_path):
    completed = _run("--ticker", "VCB", "--timeframe", "1 ngày", "--horizon-steps", "1")
    payload = json.loads(completed.stdout)

    assert payload["dag_valid"] is True
    assert "storage_persistence" not in payload
    assert not any(tmp_path.iterdir())


def test_cli_load_storage_context_exits_cleanly(tmp_path):
    write_dataset_records(
        str(tmp_path),
        "market_bars",
        (
            {
                "ticker": "VCB",
                "timeframe": "1d",
                "timestamp": "2026-01-01T00:00:00+07:00",
                "open": 1,
                "high": 2,
                "low": 1,
                "close": 2,
                "volume": 100,
            },
        ),
        ticker="VCB",
        timeframe="1d",
        date="2026-01-01",
    )

    completed = _run(
        "--ticker",
        "VCB",
        "--timeframe",
        "1 ngày",
        "--horizon-steps",
        "1",
        "--storage-root",
        str(tmp_path),
        "--storage-date",
        "2026-01-01",
        "--load-storage-context",
    )
    payload = json.loads(completed.stdout)

    assert payload["final_state"]["storage_context_status"] == "provided"
    assert payload["final_state"]["market_bar_count"] == 1
    assert payload["final_state"]["local_storage_available"] is True


def test_cli_persist_run_writes_only_under_temp_root(tmp_path):
    completed = _run(
        "--ticker",
        "VCB",
        "--timeframe",
        "1 ngày",
        "--horizon-steps",
        "1",
        "--storage-root",
        str(tmp_path),
        "--persist-run",
    )
    payload = json.loads(completed.stdout)
    persistence = payload["storage_persistence"]

    assert persistence["records_written"] == 3
    for write_result in persistence["write_results"].values():
        assert Path(write_result["actual_path"]).is_relative_to(tmp_path)
    assert any(tmp_path.iterdir())
