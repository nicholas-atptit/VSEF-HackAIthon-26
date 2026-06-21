from src.hackaithon_mvp.dag_forecast_output_verification import (
    build_dag_forecast_verification_cases,
    render_dag_forecast_verification_table,
    run_dag_forecast_verification_cases,
)


def _case_by_id(result: dict, case_id: str) -> dict:
    return next(row for row in result["cases"] if row["case_id"] == case_id)


def test_dag_verification_cases_include_demo_and_vcb_with_policy_variants():
    cases = build_dag_forecast_verification_cases()

    assert {case["ticker"] for case in cases} == {"DEMO", "VCB"}
    assert {case["policy_demo"] for case in cases} == {None, "h40"}
    assert len(cases) == 4


def test_dag_verification_outputs_expected_static_categories():
    result = run_dag_forecast_verification_cases()
    demo_no_policy = _case_by_id(result, "demo_no_policy")
    vcb_no_policy = _case_by_id(result, "vcb_no_policy")

    assert result["verification_status"] == "completed"
    assert demo_no_policy["forecast_diagnostic"] == "insufficient_evidence"
    assert demo_no_policy["route"] == "evidence_insufficient"
    assert demo_no_policy["risk_level"] == "high"
    assert vcb_no_policy["forecast_diagnostic"] == "neutral_or_uncertain"
    assert vcb_no_policy["route"] == "maintain_watchlist_review"
    assert vcb_no_policy["risk_level"] == "low"


def test_h40_policy_preserves_non_directional_dag_state():
    result = run_dag_forecast_verification_cases()

    for case_id in ("demo_h40_policy", "vcb_h40_policy"):
        row = _case_by_id(result, case_id)
        assert row["policy_runtime_status"] == "non_directional_preserved"
        assert row["forecast_diagnostic"] == row["pre_policy_forecast_diagnostic"]
        assert row["policy_id"] == "quant_core_policy.h40.eligible_slice_gate.v1"


def test_dag_verification_report_renders_compact_table():
    result = run_dag_forecast_verification_cases()
    report = render_dag_forecast_verification_table(result)

    assert "# DAG Forecast Output Verification" in report
    assert "demo_no_policy" in report
    assert "vcb_h40_policy" in report
    assert "Human review remains required." in report
