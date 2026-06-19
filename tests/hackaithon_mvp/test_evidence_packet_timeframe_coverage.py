import pytest

from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain
from src.hackaithon_mvp.evidence_packet import build_evidence_packet
from src.hackaithon_mvp.timeframe_schema import REQUIRED_TIMEFRAME_INPUTS, normalize_timeframe, timeframe_unit


@pytest.mark.parametrize("timeframe", REQUIRED_TIMEFRAME_INPUTS)
def test_evidence_packet_covers_required_timeframes(timeframe):
    chain_output = run_diagnostic_chain("VCB", sample_size=20, timeframe=timeframe)
    packet = build_evidence_packet(chain_output, run_metadata={"run_id": f"unit-{normalize_timeframe(timeframe)}"})

    assert packet["timeframe"] == normalize_timeframe(timeframe)
    assert packet["timeframe_unit"] == timeframe_unit(timeframe)
    assert packet["run_mode"] == "static_local_review"
    assert packet["human_review_required"] is True
    assert "provider access disabled" in packet["warnings"]
    assert "model training disabled" in packet["warnings"]
    assert "model inference disabled" in packet["warnings"]
    assert "benchmark rerun disabled" in packet["warnings"]
