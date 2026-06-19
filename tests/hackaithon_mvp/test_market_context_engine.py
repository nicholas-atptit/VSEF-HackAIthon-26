from src.hackaithon_mvp.diagnostic_chain.market_context_engine import run_market_context


def test_market_context_is_static_placeholder():
    output = run_market_context("VCB")
    assert output["market_context_status"] == "static_placeholder"
    assert output["live_context_enabled"] is False
    assert output["context_label"] == "local_context_unavailable"
