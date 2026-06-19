import pytest

from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain
from src.hackaithon_mvp.diagnostic_chain.quant_core_engine import run_quant_core
from src.hackaithon_mvp.timeframe_schema import normalize_timeframe, timeframe_unit


REQUIRED_TIMEFRAME_INPUTS = (
    "1p",
    "2p",
    "5p",
    "10p",
    "1h",
    "2h",
    "5h",
    "10h",
    "1 ngày",
    "2 ngày",
    "3 ngày",
    "4 ngày",
    "5 ngày",
    "10 ngày",
    "15 ngày",
    "20 ngày",
    "30 ngày",
    "40 ngày",
)

STATIC_RUNTIME_WARNINGS = {
    "static local sample evidence only",
    "provider access disabled",
    "model training disabled",
    "model inference disabled",
    "benchmark rerun disabled",
}


@pytest.mark.parametrize("timeframe", REQUIRED_TIMEFRAME_INPUTS)
def test_quant_core_and_diagnostic_chain_cover_required_timeframes(timeframe):
    canonical = normalize_timeframe(timeframe)
    expected_unit = timeframe_unit(timeframe)

    quant_output = run_quant_core("VCB", sample_size=20, timeframe=timeframe)

    assert quant_output["timeframe"] == canonical
    assert quant_output["timeframe_unit"] == expected_unit
    assert STATIC_RUNTIME_WARNINGS.issubset(set(quant_output["warnings"]))

    chain_output = run_diagnostic_chain("VCB", sample_size=20, timeframe=timeframe)

    assert chain_output["timeframe"] == canonical
    assert chain_output["layer_1_quant_core"]["timeframe"] == canonical
    assert chain_output["layer_1_quant_core"]["timeframe_unit"] == expected_unit
    assert STATIC_RUNTIME_WARNINGS.issubset(set(chain_output["layer_1_quant_core"]["warnings"]))
    assert chain_output["layer_5_market_context"]["live_context_enabled"] is False
    assert chain_output["layer_6_calibration"]["fine_tuning_performed"] is False
