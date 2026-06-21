from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.ml_diagnostic_engine import run_ml_diagnostic_engine
from src.hackaithon_mvp.scenario_engine_v2 import (
    build_scenario_registry_v2,
    run_scenario_engine_v2,
    validate_scenario_context,
)


def test_scenario_engine_v2_has_all_required_cases():
    scenario_ids = {row["scenario_id"] for row in build_scenario_registry_v2()}

    assert scenario_ids == {
        "base_case",
        "missing_evidence_case",
        "high_uncertainty_case",
        "model_disagreement_case",
        "calibration_stress_case",
        "data_quality_stress_case",
    }


def test_scenario_engine_v2_base_case_is_stable():
    payload = build_minimal_engine_input_fixture()
    ml_summary = run_ml_diagnostic_engine(tuple(payload["model_diagnostics"]))

    result = run_scenario_engine_v2(payload=payload, ml_summary=ml_summary)

    assert result["dominant_scenario"] == "base_case"
    assert result["scenario_risk_level"] == "low"
    assert result["stability_status"] == "stable"


def test_missing_evidence_dominates_scenario():
    payload = build_minimal_engine_input_fixture()
    payload["market_bars"] = []
    payload["forecast_rows"] = []
    payload["model_diagnostics"] = []
    payload["scenario_context"]["evidence_status"] = "missing"

    result = run_scenario_engine_v2(payload=payload)

    assert result["dominant_scenario"] == "missing_evidence_case"
    assert result["stability_status"] == "insufficient_evidence"
    assert result["required_human_review"] is True


def test_scenario_context_rejects_live_provider_fields():
    result = validate_scenario_context({"provider_api": "disabled"})

    assert result["is_valid"] is False
    assert result["errors"]
