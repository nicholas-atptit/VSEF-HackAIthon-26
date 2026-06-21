import subprocess
import sys
from copy import deepcopy

from src.hackaithon_mvp.decision_lane_v2 import run_decision_lane_v2
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.ml_diagnostic_engine import run_ml_diagnostic_engine
from src.hackaithon_mvp.risk_engine_v3 import (
    build_risk_engine_v3_config,
    run_risk_engine_v3,
)
from src.hackaithon_mvp.scenario_engine_v2 import run_scenario_engine_v2


def test_risk_engine_v3_config_lists_dimensions():
    config = build_risk_engine_v3_config()

    assert config["risk_engine_version"] == "v3"
    assert "liquidity_risk" in config["risk_dimensions"]
    assert "evidence_consistency_risk" in config["risk_dimensions"]


def test_risk_v3_detects_low_liquidity():
    payload = build_minimal_engine_input_fixture()
    for bar in payload["market_bars"]:
        bar["volume"] = 0

    result = run_risk_engine_v3(payload=payload)

    assert result["risk_dimensions"]["liquidity_risk"]["risk_level"] in {"high", "critical"}
    assert "near_zero_volume" in result["risk_dimensions"]["liquidity_risk"]["flags"]


def test_risk_v3_detects_suspicious_repeated_ohlcv():
    payload = build_minimal_engine_input_fixture()
    payload["market_bars"].append(deepcopy(payload["market_bars"][0]))
    payload["market_bars"][-1]["timestamp"] = "2026-06-21T00:00:00+07:00"

    result = run_risk_engine_v3(payload=payload)

    assert result["risk_dimensions"]["manipulation_susceptibility_risk"]["risk_level"] in {"high", "critical"}
    assert "repeated_identical_ohlcv" in result["risk_dimensions"]["manipulation_susceptibility_risk"]["flags"]


def test_risk_v3_detects_volatility_and_gap_risk():
    payload = build_minimal_engine_input_fixture()
    payload["market_bars"][0]["high"] = 160
    payload["market_bars"][0]["low"] = 60
    payload["market_bars"][1]["timestamp"] = "2026-07-15T00:00:00+07:00"

    result = run_risk_engine_v3(payload=payload)

    dimension = result["risk_dimensions"]["volatility_gap_risk"]
    assert dimension["risk_level"] in {"high", "critical"}
    assert any(flag in dimension["flags"] for flag in ("large_timestamp_gap", "bar_0_extreme_range"))


def test_risk_v3_detects_evidence_consistency_risk():
    payload = build_minimal_engine_input_fixture()
    ml_summary = run_ml_diagnostic_engine(tuple(payload["model_diagnostics"]))
    scenario_summary = {
        "scenario_risk_level": "high",
        "stability_status": "unstable",
        "claim_boundary": {},
        "non_claim": "scenario test",
    }

    result = run_risk_engine_v3(payload=payload, ml_summary=ml_summary, scenario_summary=scenario_summary)

    assert result["risk_dimensions"]["evidence_consistency_risk"]["risk_level"] in {"high", "critical"}
    assert "ml_scenario_consistency_conflict" in result["risk_dimensions"]["evidence_consistency_risk"]["flags"]


def test_critical_risk_v3_blocks_decision_lane_v2():
    payload = build_minimal_engine_input_fixture()
    payload["market_bars"][0]["high"] = 1
    ml_summary = run_ml_diagnostic_engine(tuple(payload["model_diagnostics"]))
    scenario_summary = run_scenario_engine_v2(payload=payload, ml_summary=ml_summary)
    risk_summary = run_risk_engine_v3(payload=payload, ml_summary=ml_summary, scenario_summary=scenario_summary)
    decision = run_decision_lane_v2(
        diagnostic_output={"forecast_diagnostic": "neutral_or_uncertain"},
        ml_summary=ml_summary,
        risk_summary=risk_summary,
        scenario_summary=scenario_summary,
    )

    assert risk_summary["risk_level"] == "critical"
    assert decision["lane"] == "blocked_pending_risk_review"


def test_risk_engine_v3_cli_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.risk_engine_v3"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert '"risk_engine_version": "v3"' in completed.stdout
