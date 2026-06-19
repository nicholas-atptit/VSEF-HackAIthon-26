from src.hackaithon_mvp.diagnostic_chain.chain_schema import ALLOWED_SCENARIOS
from src.hackaithon_mvp.diagnostic_chain.scenario_engine import run_scenario_engine


def test_scenario_engine_returns_uncertain_for_insufficient_evidence():
    output = run_scenario_engine({"quant_signal": "insufficient_evidence", "consensus_strength": 0.0})
    assert output["scenario"] == "uncertain"
    assert output["scenario"] in ALLOWED_SCENARIOS


def test_scenario_engine_maps_positive_bias_to_growth_when_not_weak():
    output = run_scenario_engine({"quant_signal": "positive_bias", "consensus_strength": 0.3})
    assert output["scenario"] == "growth"
    assert set(output["scenario_probabilities"]) == ALLOWED_SCENARIOS


def test_scenario_engine_keeps_weak_signal_conservative():
    output = run_scenario_engine({"quant_signal": "negative_bias", "consensus_strength": 0.01})
    assert output["scenario"] == "uncertain"
