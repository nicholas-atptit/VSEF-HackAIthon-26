import subprocess
import sys

from src.hackaithon_mvp.diagnostic_engine_hardening_gate import (
    render_diagnostic_engine_hardening_report,
    run_diagnostic_engine_hardening_gate,
)


def test_diagnostic_engine_hardening_gate_accepted():
    result = run_diagnostic_engine_hardening_gate()

    assert result["hardening_status"] == "accepted_for_gateway_ready_local_engine_core"
    assert result["passed_count"] == result["check_count"]
    assert all(check["passed"] for check in result["checks"])


def test_hardening_gate_report_renders_status():
    report = render_diagnostic_engine_hardening_report(run_diagnostic_engine_hardening_gate())

    assert "Diagnostic Engine Hardening Gate" in report
    assert "accepted_for_gateway_ready_local_engine_core" in report
    assert "Human review remains required." in report


def test_hardening_gate_cli_report_exits_cleanly():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.diagnostic_engine_hardening_gate",
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Checks passed:" in completed.stdout
