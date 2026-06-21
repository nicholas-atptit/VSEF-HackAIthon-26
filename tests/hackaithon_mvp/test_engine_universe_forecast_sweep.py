from src.hackaithon_mvp.engine_universe_forecast_sweep import (
    EXPECTED_ENGINE_UNIVERSE_TOTAL,
    build_engine_universe_sweep_plan,
    render_engine_universe_sweep_report,
    run_engine_universe_forecast_sweep,
    summarize_engine_universe_sweep,
)


def test_sweep_plan_discovers_baseline_auxiliary_and_stack_specs():
    plan = build_engine_universe_sweep_plan(limit=100)

    assert plan["total_specs_discovered"] == EXPECTED_ENGINE_UNIVERSE_TOTAL
    assert plan["planned_attempts"] == 100
    counts = {entry["public_name"]: entry["spec_count"] for entry in plan["catalogs"]}
    assert counts == {
        "baseline": 32850,
        "auxiliary": 22500,
        "stack": 22500,
    }
    assert all(entry["runner_available"] for entry in plan["catalogs"])
    assert all(entry["returns_tuple"] for entry in plan["catalogs"])
    assert not any(entry["streaming_generator_style"] for entry in plan["catalogs"])


def test_limited_sweep_runs_and_summarizes_distributions():
    summary = run_engine_universe_forecast_sweep(limit=120, sample_size=7)

    assert summary["total_specs_discovered"] == EXPECTED_ENGINE_UNIVERSE_TOTAL
    assert summary["total_specs_attempted"] == 120
    assert summary["completed_count"] + summary["skipped_count"] + summary["failed_count"] == 120
    assert summary["diagnostic_distribution"]
    assert summary["route_distribution"]
    assert summary["risk_distribution"]
    assert summary["family_distribution"]
    assert summary["horizon_distribution"]
    assert summary["skip_reason_distribution"]
    assert 0.0 <= summary["coverage_ratio"] <= 1.0
    assert 0.0 <= summary["failure_ratio"] <= 1.0
    assert 0 < len(summary["representative_samples"]) <= 7
    assert summary["claim_boundary_flags"]["live_data_enabled"] is False
    assert summary["claim_boundary_flags"]["provider_calls_enabled"] is False
    assert summary["claim_boundary_flags"]["training_enabled"] is False
    assert summary["claim_boundary_flags"]["live_inference_enabled"] is False
    assert summary["claim_boundary_flags"]["benchmark_rerun"] is False


def test_sweep_can_include_auxiliary_and_stack_in_bounded_run():
    baseline_summary = run_engine_universe_forecast_sweep(
        limit=1,
        include_baseline=True,
        include_auxiliary=False,
        include_stack=False,
    )
    auxiliary_summary = run_engine_universe_forecast_sweep(
        limit=1,
        include_baseline=False,
        include_auxiliary=True,
        include_stack=False,
    )
    stack_summary = run_engine_universe_forecast_sweep(
        limit=1,
        include_baseline=False,
        include_auxiliary=False,
        include_stack=True,
    )

    assert baseline_summary["family_distribution"]
    assert auxiliary_summary["family_distribution"]
    assert stack_summary["family_distribution"]
    assert auxiliary_summary["skipped_count"] == 1
    assert stack_summary["skipped_count"] == 1


def test_per_engine_failure_does_not_abort_summary(monkeypatch):
    from src.hackaithon_mvp import engine_universe_forecast_sweep as sweep

    calls = {"count": 0}
    original = sweep._compact_engine_result

    def flaky(spec, evidence_records):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("forced local failure")
        return original(spec, evidence_records)

    monkeypatch.setattr(sweep, "_compact_engine_result", flaky)
    summary = sweep.run_engine_universe_forecast_sweep(limit=3)

    assert summary["total_specs_attempted"] == 3
    assert summary["failed_count"] == 1
    assert summary["sweep_status"] == "completed_with_engine_failures"


def test_summarize_engine_universe_sweep_accepts_compact_results():
    summary = summarize_engine_universe_sweep(
        (
            {
                "execution_status": "completed",
                "forecast_diagnostic": "neutral_or_uncertain",
                "route": None,
                "risk_level": None,
                "engine_family": "classification",
                "horizon": 40,
                "skip_reason": None,
            },
            {
                "execution_status": "skipped_missing_evidence",
                "forecast_diagnostic": "insufficient_evidence",
                "route": None,
                "risk_level": None,
                "engine_family": "baseline",
                "horizon": 1,
                "skip_reason": "missing static evidence",
            },
        )
    )

    assert summary["total_specs_attempted"] == 2
    assert summary["completed_count"] == 1
    assert summary["skipped_count"] == 1
    assert summary["diagnostic_distribution"]["insufficient_evidence"] == 1
    assert summary["skip_reason_distribution"]["missing static evidence"] == 1


def test_sweep_report_renders_static_boundary():
    report = render_engine_universe_sweep_report(run_engine_universe_forecast_sweep(limit=5))

    assert "Engine Universe Forecast Diagnostic Sweep" in report
    assert "Total specs discovered: 77850" in report
    assert "does not train models" in report
    assert "Raw sweep outputs are generated artifacts" in report
