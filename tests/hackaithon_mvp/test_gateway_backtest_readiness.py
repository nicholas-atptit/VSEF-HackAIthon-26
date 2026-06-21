import subprocess
import sys

from src.hackaithon_mvp.gateway_backtest_readiness import (
    render_gateway_backtest_readiness_report,
    run_gateway_backtest_readiness_gate,
)


def test_gateway_backtest_readiness_gate_passes():
    result = run_gateway_backtest_readiness_gate()

    assert result["readiness_status"] == "ready_for_offline_gateway_backtest_and_fine_tune_control"
    assert result["passed_count"] == result["check_count"]
    assert result["llm_record_count"] > 0
    assert result["auto_execution_allowed"] is False
    assert result["auto_training_allowed"] is False


def test_gateway_backtest_readiness_report_renders_status():
    report = render_gateway_backtest_readiness_report(run_gateway_backtest_readiness_gate())

    assert "# Gateway Backtest Readiness" in report
    assert "ready_for_offline_gateway_backtest_and_fine_tune_control" in report
    assert "Risk Engine V3:" in report


def test_gateway_backtest_readiness_cli_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.gateway_backtest_readiness", "--format", "report"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "ready_for_offline_gateway_backtest_and_fine_tune_control" in completed.stdout
