from src.hackaithon_mvp.diagnostic_chain.chain_schema import ALLOWED_QUANT_SIGNALS
from src.hackaithon_mvp.diagnostic_chain.quant_core_engine import MAX_BASELINE_SAMPLE_SIZE, run_quant_core


def test_quant_core_runs_bounded_static_sample_for_vcb():
    output = run_quant_core("VCB", sample_size=500)
    assert output["ticker"] == "VCB"
    assert output["quant_signal"] in ALLOWED_QUANT_SIGNALS
    assert output["engine_count_checked"] <= MAX_BASELINE_SAMPLE_SIZE
    assert output["completed_count"] >= 1
    assert output["skipped_missing_evidence_count"] >= 1


def test_quant_core_caps_sample_size_and_omits_full_spec_listing():
    output = run_quant_core("VCB", sample_size=999999)
    assert output["engine_count_checked"] == MAX_BASELINE_SAMPLE_SIZE
    assert "engine_ids" not in output
    assert any("capped" in warning for warning in output["warnings"])


def test_quant_core_handles_missing_ticker_evidence_safely():
    output = run_quant_core("ZZZ", sample_size=25)
    assert output["quant_signal"] == "insufficient_evidence"
    assert output["completed_count"] == 0
    assert output["skipped_missing_evidence_count"] == output["engine_count_checked"]
