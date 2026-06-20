import json
import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.end_to_end_demo", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_cli_default_exits_cleanly():
    completed = _run()
    payload = json.loads(completed.stdout)

    assert payload["demo_status"] == "completed"
    assert payload["storage_write_enabled"] is False
    assert payload["actual_outcome_rows"] == 1


def test_cli_report_exits_cleanly():
    completed = _run("--format", "report")

    assert "End-to-End Local Demo" in completed.stdout
    assert "Demo status: completed" in completed.stdout
    assert "No operational decision is produced." in completed.stdout


def test_cli_policy_demo_h40_exits_cleanly():
    completed = _run("--policy-demo", "h40")
    payload = json.loads(completed.stdout)

    assert payload["demo_status"] == "completed"
    assert payload["policy_demo"] == "h40"
    assert payload["policy_metadata"]["policy_id"] == "quant_core_policy.h40.eligible_slice_gate.v1"


def test_cli_persist_exits_cleanly_under_temp_root(tmp_path):
    completed = _run("--persist", "--storage-root", str(tmp_path))
    payload = json.loads(completed.stdout)

    assert payload["demo_status"] == "completed"
    assert payload["storage_write_enabled"] is True
    assert payload["records_written"] == 2
    assert str(payload["storage_root"]).startswith(str(tmp_path).replace("\\", "/"))
