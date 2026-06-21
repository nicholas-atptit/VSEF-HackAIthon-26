import json
import subprocess
import sys

from src.hackaithon_mvp.periodic_diagnostic_runner import (
    build_periodic_runner_plan,
    run_periodic_diagnostic_loop,
    run_periodic_diagnostic_once,
)


def test_periodic_runner_defaults_to_one_iteration_dry_run_no_writes():
    plan = build_periodic_runner_plan()

    assert plan["interval_seconds"] == 60
    assert plan["max_iterations"] == 1
    assert plan["dry_run_default"] is True
    assert plan["background_process"] is False
    assert plan["writes_files_by_default"] is False


def test_periodic_runner_once_uses_static_dag_without_runtime_integrations():
    result = run_periodic_diagnostic_once()

    assert result["runner_status"] == "completed"
    assert result["ticker"] == "DEMO"
    assert result["forecast_diagnostic"] == "insufficient_evidence"
    assert result["writes_performed"] is False
    assert result["live_data_used"] is False
    assert result["provider_calls_used"] is False
    assert result["training_used"] is False
    assert result["inference_used"] is False
    assert result["benchmark_rerun"] is False


def test_periodic_runner_loop_is_bounded_by_default():
    result = run_periodic_diagnostic_loop()

    assert result["loop_status"] == "completed"
    assert result["dry_run"] is True
    assert result["iteration_count"] == 1
    assert result["sleep_performed"] is False
    assert result["background_process"] is False


def test_periodic_runner_cli_modes_exit_cleanly():
    commands = (
        [sys.executable, "-m", "src.hackaithon_mvp.periodic_diagnostic_runner", "--plan"],
        [sys.executable, "-m", "src.hackaithon_mvp.periodic_diagnostic_runner", "--once"],
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.periodic_diagnostic_runner",
            "--max-iterations",
            "1",
            "--dry-run",
        ],
    )
    for command in commands:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        json.loads(completed.stdout)
