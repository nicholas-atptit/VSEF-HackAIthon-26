import subprocess
import sys

from src.hackaithon_mvp.engine_universe_sweep_readiness import (
    READY_STATUS,
    get_engine_universe_sweep_command_metadata,
    render_engine_universe_sweep_readiness_report,
    run_engine_universe_sweep_readiness_gate,
)


def test_engine_universe_sweep_readiness_gate_passes():
    result = run_engine_universe_sweep_readiness_gate()

    assert result["readiness_status"] == READY_STATUS
    assert all(check["passed"] for check in result["checks"])
    assert result["plan"]["total_specs_discovered"] == 77850
    assert result["limited_sweep_summary"]["total_specs_attempted"] == 100
    assert result["limited_sweep_summary"]["representative_samples"]


def test_engine_universe_sweep_command_metadata_is_safe():
    commands = get_engine_universe_sweep_command_metadata()

    assert commands
    for command in commands:
        assert command["requires_live_data"] is False
        assert command["requires_provider"] is False
        assert command["runs_training"] is False
        assert command["runs_live_inference"] is False
        assert command["runs_benchmark"] is False
    default_commands = [command for command in commands if not command["writes_files"]]
    assert default_commands
    assert all(command["writes_files"] is False for command in default_commands)


def test_engine_universe_sweep_readiness_report_renders_status():
    report = render_engine_universe_sweep_readiness_report(run_engine_universe_sweep_readiness_gate())

    assert "Engine Universe Sweep Readiness" in report
    assert READY_STATUS in report
    assert "Default commands do not write files" in report


def test_engine_universe_sweep_readiness_cli_exits_cleanly():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.engine_universe_sweep_readiness",
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_STATUS in completed.stdout
