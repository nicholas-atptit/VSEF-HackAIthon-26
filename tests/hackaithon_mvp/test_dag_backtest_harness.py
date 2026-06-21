import subprocess
import sys

from src.hackaithon_mvp.dag_backtest_harness import (
    build_dag_backtest_fixture,
    render_dag_backtest_report,
    run_dag_backtest_from_local_bars,
    run_dag_backtest_from_payloads,
)


def _bars() -> tuple[dict, ...]:
    return (
        {"ticker": "DEMO", "timestamp": "2026-01-01", "open": 100, "high": 105, "low": 99, "close": 102, "volume": 100000},
        {"ticker": "DEMO", "timestamp": "2026-01-02", "open": 102, "high": 106, "low": 101, "close": 104, "volume": 120000},
        {"ticker": "DEMO", "timestamp": "2026-01-03", "open": 104, "high": 107, "low": 103, "close": 106, "volume": 130000},
        {"ticker": "DEMO", "timestamp": "2026-01-04", "open": 106, "high": 108, "low": 105, "close": 107, "volume": 110000},
    )


def test_dag_backtest_fixture_runs():
    fixture = build_dag_backtest_fixture()
    result = run_dag_backtest_from_payloads(payloads=tuple(fixture["payloads"]))

    assert result["backtest_status"] == "completed"
    assert result["engine_run_count"] == 1
    assert result["engine_completion_rate"] == 1.0


def test_dag_backtest_from_local_bars_has_no_auto_execution():
    result = run_dag_backtest_from_local_bars(bars=_bars(), ticker="DEMO")

    assert result["backtest_status"] == "completed"
    assert result["engine_run_count"] >= 1
    assert result["auto_execution_count"] == 0
    assert result["human_review_count"] == result["engine_run_count"]


def test_dag_backtest_report_renders_local_boundary():
    result = run_dag_backtest_from_payloads(payloads=tuple(build_dag_backtest_fixture()["payloads"]))
    report = render_dag_backtest_report(result)

    assert "# DAG Backtest Harness" in report
    assert "Auto execution count: 0" in report
    assert "not a benchmark rerun" in report


def test_dag_backtest_cli_fixture_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.dag_backtest_harness", "--fixture", "--format", "report"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "DAG Backtest Harness" in completed.stdout
