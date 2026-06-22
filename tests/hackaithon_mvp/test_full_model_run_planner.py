from src.hackaithon_mvp.full_model_run_planner import (
    build_full_model_run_plan,
    inspect_available_training_inputs,
    render_full_model_run_plan_report,
)


def test_planner_finds_runnable_groups_when_local_bars_exist(tmp_path):
    path = tmp_path / "AAA.csv"
    path.write_text(
        "date,ticker,open,high,low,close,volume\n2025-01-01,AAA,1,2,1,2,100\n",
        encoding="utf-8",
    )

    result = build_full_model_run_plan(repo_root=str(tmp_path), max_tickers=1)

    assert result["plan_status"] == "ready"
    assert result["runnable_baseline_specs"]
    assert "write generated outputs only under .tmp_full_model_run" in result["safe_execution_plan"]


def test_planner_blocks_without_local_bars(tmp_path):
    result = build_full_model_run_plan(repo_root=str(tmp_path))

    assert result["plan_status"] == "blocked_by_data_unavailability"
    assert "local_ohlcv_sources_missing" in result["blocked_specs_by_reason"]


def test_input_inspection_and_report_render(tmp_path):
    inspection = inspect_available_training_inputs(repo_root=str(tmp_path))
    report = render_full_model_run_plan_report(build_full_model_run_plan(repo_root=str(tmp_path)))

    assert inspection["inspection_status"] == "completed"
    assert "Full Local Model Run Plan" in report
