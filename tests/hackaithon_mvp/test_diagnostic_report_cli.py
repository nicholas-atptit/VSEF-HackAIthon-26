import subprocess
import sys


def test_diagnostic_report_cli_prints_report_and_exits_cleanly():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.diagnostic_report",
            "--ticker",
            "VCB",
            "--sample-size",
            "20",
            "--timeframe",
            "1 ngày",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "# HackAIthon MVP Diagnostic Routing Report" in completed.stdout
    assert "Timeframe: 1d (day)" in completed.stdout
    assert "Human review required: True" in completed.stdout


def test_diagnostic_report_cli_write_flag_writes_requested_path(tmp_path):
    output_path = tmp_path / "reports" / "latest_report.md"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.diagnostic_report",
            "--ticker",
            "VCB",
            "--sample-size",
            "20",
            "--timeframe",
            "1 ngày",
            "--write",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    file_text = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert "Timeframe: 1d (day)" in completed.stdout
    assert "Timeframe: 1d (day)" in file_text
    assert list(tmp_path.rglob("*_report.md")) == [output_path]
