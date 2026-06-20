import json
import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.local_storage.storage_cli", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_cli_capability_exits_cleanly():
    completed = _run("--capability")
    payload = json.loads(completed.stdout)

    assert "parquet_engine_available" in payload
    assert payload["claim_boundary"]["live_data_enabled"] is False


def test_cli_demo_write_and_read_under_temp_root(tmp_path):
    write_completed = _run("--demo-write", "--root", str(tmp_path))
    write_payload = json.loads(write_completed.stdout)
    read_completed = _run("--demo-read", "--root", str(tmp_path))
    read_payload = json.loads(read_completed.stdout)

    assert write_payload["row_count"] == 2
    assert write_payload["actual_path"].endswith((".parquet", ".jsonl"))
    assert read_payload["read_row_count"] == 2
    assert read_payload["availability_index"]["group_count"] == 1
