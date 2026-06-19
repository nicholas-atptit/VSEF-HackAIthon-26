import json
import subprocess
import sys

from src.hackaithon_mvp.diagnostic_chain.chain_schema import ALLOWED_ROUTES
from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain


def test_orchestrator_runs_for_vcb():
    output = run_diagnostic_chain("VCB", sample_size=500)
    assert output["ticker"] == "VCB"
    assert output["layer_1_quant_core"]["engine_count_checked"] <= 500
    assert output["layer_5_market_context"]["live_context_enabled"] is False
    assert output["layer_6_calibration"]["fine_tuning_performed"] is False
    assert output["layer_7_portfolio_diagnostic_allocator"]["allocation_is_advisory"] is False
    assert output["layer_8_phase_router"]["route"] in ALLOWED_ROUTES


def test_orchestrator_cli_returns_json_for_vcb():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator",
            "--ticker",
            "VCB",
            "--sample-size",
            "25",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)
    assert output["ticker"] == "VCB"
    assert output["layer_1_quant_core"]["engine_count_checked"] <= 25
