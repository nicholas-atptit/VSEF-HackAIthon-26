from src.hackaithon_mvp.diagnostic_chain.chain_schema import assert_no_forbidden_public_terms
from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain


def test_final_diagnostic_chain_output_has_no_forbidden_public_terms():
    output = run_diagnostic_chain("VCB", sample_size=50)
    assert_no_forbidden_public_terms(output)


def test_final_output_states_static_disabled_runtime_behaviors():
    output = run_diagnostic_chain("VCB", sample_size=50)
    warnings = output["layer_1_quant_core"]["warnings"]
    assert "provider access disabled" in warnings
    assert "model training disabled" in warnings
    assert "model inference disabled" in warnings
    assert "benchmark rerun disabled" in warnings
    assert output["layer_5_market_context"]["live_context_enabled"] is False
    assert output["layer_6_calibration"]["fine_tuning_performed"] is False
