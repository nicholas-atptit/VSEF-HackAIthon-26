from src.hackaithon_mvp.dag_backtest_harness import (
    build_dag_backtest_fixture,
    render_dag_backtest_report,
    run_dag_backtest_from_local_bars,
    run_dag_backtest_from_payloads,
)


def _bar(index: int) -> dict:
    price = 100 + index
    return {
        "ticker": "DEMO",
        "timestamp": f"2026-01-{index + 1:02d}",
        "open": price,
        "high": price + 2,
        "low": price - 1,
        "close": price + 1,
        "volume": 1000 + index,
    }


def test_tiny_fixture_runs():
    result = run_dag_backtest_from_payloads(payloads=tuple(build_dag_backtest_fixture()["payloads"]))

    assert result["backtest_status"] == "completed"
    assert result["engine_run_count"] == 1


def test_rolling_windows_with_insufficient_bars_runs_one_payload():
    result = run_dag_backtest_from_local_bars(bars=(_bar(0),), ticker="DEMO")

    assert result["backtest_status"] == "completed"
    assert result["engine_run_count"] == 1


def test_multiple_payloads_run_and_human_review_count_equals_run_count():
    payload = build_dag_backtest_fixture()["payloads"][0]
    result = run_dag_backtest_from_payloads(payloads=(payload, payload))

    assert result["backtest_status"] == "completed"
    assert result["engine_run_count"] == 2
    assert result["human_review_count"] == result["engine_run_count"]
    assert result["auto_execution_count"] == 0


def test_one_invalid_payload_does_not_abort_whole_harness():
    payload = build_dag_backtest_fixture()["payloads"][0]
    result = run_dag_backtest_from_payloads(payloads=(payload, "bad-payload", payload))

    assert result["backtest_status"] == "completed_with_errors"
    assert result["engine_run_count"] == 2
    assert result["errors"]


def test_report_has_no_benchmark_performance_claim():
    report = render_dag_backtest_report(run_dag_backtest_from_payloads(payloads=tuple(build_dag_backtest_fixture()["payloads"])))
    lowered = report.lower()

    assert "not a benchmark rerun" in lowered
    assert "execution backtest" in lowered


def test_optional_evaluation_only_when_future_bars_exist():
    payload = build_dag_backtest_fixture()["payloads"][0]
    no_eval = run_dag_backtest_from_payloads(payloads=(payload,))
    with_actual = dict(payload)
    with_actual["forecast_rows"] = [
        {
            "ticker": "DEMO",
            "timeframe": "1d",
            "prediction_timestamp": "2026-01-01T00:00:00+07:00",
            "horizon_steps": 1,
            "forecast_diagnostic": "positive_bias",
            "actual_future_return": 0.01,
            "actual_direction_label": "positive",
        }
    ]
    with_eval = run_dag_backtest_from_payloads(payloads=(with_actual,))

    assert no_eval["evaluation_summary"] is None
    assert with_eval["evaluation_summary"]["actual_data_status"] == "provided"
