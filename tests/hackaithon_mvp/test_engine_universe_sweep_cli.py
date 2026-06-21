import json
import subprocess
import sys
from pathlib import Path


def test_default_cli_exits_cleanly_and_does_not_write(tmp_path):
    before = set(tmp_path.iterdir())
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.engine_universe_forecast_sweep",
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    after = set(tmp_path.iterdir())

    assert "Total specs attempted: 100" in completed.stdout
    assert before == after


def test_limit_cli_json_exits_cleanly():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.engine_universe_forecast_sweep",
            "--limit",
            "25",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["total_specs_attempted"] == 25
    assert payload["total_specs_discovered"] == 77850
    assert payload["writes_files_by_default"] is False


def test_explicit_write_summary_writes_only_requested_temp_file(tmp_path):
    output_path = tmp_path / "summary.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.engine_universe_forecast_sweep",
            "--limit",
            "10",
            "--format",
            "json",
            "--write-summary",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stdout_payload = json.loads(completed.stdout)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.exists()
    assert stdout_payload["total_specs_attempted"] == 10
    assert file_payload["total_specs_attempted"] == 10
    assert sorted(path.name for path in tmp_path.iterdir()) == ["summary.json"]


def test_full_cli_can_be_bounded_by_excluding_all_catalogs():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.engine_universe_forecast_sweep",
            "--full",
            "--exclude-baseline",
            "--exclude-auxiliary",
            "--exclude-stack",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["total_specs_discovered"] == 0
    assert payload["total_specs_attempted"] == 0
    assert payload["representative_samples"] == []
