import json
import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.public_demo_readiness", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_cli_json_exits_cleanly():
    completed = _run()
    payload = json.loads(completed.stdout)

    assert payload["readiness_status"] == "ready_with_manual_review"
    assert payload["demo_command_count"] == 6


def test_cli_report_exits_cleanly():
    completed = _run("--format", "report")

    assert "Public Demo Readiness" in completed.stdout
    assert "Readiness status: ready_with_manual_review" in completed.stdout
    assert "No file writes are performed." in completed.stdout


def test_cli_does_not_write_files(tmp_path):
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    completed = _run("--readme", "README.md")

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert completed.returncode == 0
    assert before == after
