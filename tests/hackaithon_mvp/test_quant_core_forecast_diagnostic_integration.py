import json
import re

from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain
from src.hackaithon_mvp.diagnostic_chain.quant_core_engine import MAX_FORECAST_DIAGNOSTIC_SAMPLE, run_quant_core


FORBIDDEN_PUBLIC_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bclient relationship\b",
)


def _assert_no_forbidden_public_terms(payload):
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in FORBIDDEN_PUBLIC_PATTERNS:
        assert re.search(pattern, text) is None, pattern


def test_quant_core_includes_forecast_diagnostic_counts():
    output = run_quant_core("VCB", sample_size=50)
    assert output["forecast_diagnostic_engine_enabled"] is True
    assert set(output["forecast_diagnostic_counts"]) == {
        "positive",
        "negative",
        "neutral",
        "insufficient",
        "exploratory",
    }
    assert sum(output["forecast_diagnostic_counts"].values()) == output["engine_count_checked"]


def test_quant_core_does_not_list_all_engine_specs():
    output = run_quant_core("VCB", sample_size=50)
    assert "engine_ids" not in output
    assert "engine_specs" not in output
    assert len(output["forecast_diagnostic_sample"]) <= MAX_FORECAST_DIAGNOSTIC_SAMPLE


def test_orchestrator_runs_for_vcb_with_forecast_diagnostic_summary():
    output = run_diagnostic_chain("VCB", sample_size=50)
    assert output["ticker"] == "VCB"
    assert output["layer_1_quant_core"]["forecast_diagnostic_engine_enabled"] is True
    assert "forecast_diagnostic_counts" in output["layer_1_quant_core"]


def test_public_outputs_have_no_corporate_or_action_attribution_language():
    output = run_diagnostic_chain("VCB", sample_size=50)
    _assert_no_forbidden_public_terms(output)
