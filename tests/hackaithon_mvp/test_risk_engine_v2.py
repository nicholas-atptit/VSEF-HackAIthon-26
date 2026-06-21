from copy import deepcopy

from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.ml_diagnostic_engine import run_ml_diagnostic_engine
from src.hackaithon_mvp.risk_engine_v2 import (
    build_risk_engine_v2_config,
    run_risk_engine_v2,
)
from src.hackaithon_mvp.scenario_engine_v2 import run_scenario_engine_v2


def _run(payload):
    ml_summary = run_ml_diagnostic_engine(tuple(payload.get("model_diagnostics", ())))
    scenario_summary = run_scenario_engine_v2(payload=payload, ml_summary=ml_summary)
    return run_risk_engine_v2(payload=payload, ml_summary=ml_summary, scenario_summary=scenario_summary)


def test_risk_engine_v2_config_lists_all_dimensions():
    config = build_risk_engine_v2_config()

    assert config["config_version"] == "2.0"
    assert "model_disagreement_risk" in config["risk_dimensions"]
    assert "missing_context_risk" in config["risk_dimensions"]


def test_risk_engine_outputs_low_medium_high_critical():
    low = _run(build_minimal_engine_input_fixture())
    medium_payload = build_minimal_engine_input_fixture()
    medium_payload["risk_context"] = {}
    medium = _run(medium_payload)
    high_payload = build_minimal_engine_input_fixture()
    high_payload["market_bars"] = []
    high_payload["forecast_rows"] = []
    high_payload["model_diagnostics"] = []
    high = _run(high_payload)
    critical_payload = build_minimal_engine_input_fixture()
    critical_payload["risk_context"]["force_critical_review"] = True
    critical = _run(critical_payload)

    assert low["risk_level"] == "low"
    assert medium["risk_level"] == "medium"
    assert high["risk_level"] == "high"
    assert critical["risk_level"] == "critical"


def test_missing_evidence_increases_risk():
    payload = build_minimal_engine_input_fixture()
    baseline = _run(payload)
    payload["market_bars"] = []
    payload["forecast_rows"] = []
    payload["model_diagnostics"] = []

    result = _run(payload)

    assert result["risk_score"] > baseline["risk_score"]
    assert result["risk_dimensions"]["evidence_coverage_risk"]["risk_level"] in {"high", "critical"}


def test_conflicting_model_diagnostics_increase_risk():
    payload = build_minimal_engine_input_fixture()
    payload["model_diagnostics"][0]["forecast_diagnostic"] = "positive_bias"
    payload["model_diagnostics"][1]["forecast_diagnostic"] = "negative_bias"

    result = _run(payload)

    assert result["risk_dimensions"]["model_disagreement_risk"]["risk_level"] == "high"
    assert result["required_human_review"] is True
    assert result["auto_execution_allowed"] is False
