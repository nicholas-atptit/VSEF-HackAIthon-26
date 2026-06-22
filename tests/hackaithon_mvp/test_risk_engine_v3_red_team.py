from copy import deepcopy
import re

from src.hackaithon_mvp.decision_lane_v2 import run_decision_lane_v2
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.ml_diagnostic_engine import run_ml_diagnostic_engine
from src.hackaithon_mvp.risk_engine_v3 import run_risk_engine_v3
from src.hackaithon_mvp.scenario_engine_v2 import run_scenario_engine_v2


def _payload():
    return build_minimal_engine_input_fixture()


def test_zero_volume_sequence_flags_high_liquidity_risk():
    payload = _payload()
    for bar in payload["market_bars"]:
        bar["volume"] = 0

    result = run_risk_engine_v3(payload=payload)

    liquidity = result["risk_dimensions"]["liquidity_risk"]
    assert liquidity["risk_level"] in {"high", "critical"}
    assert "near_zero_volume" in liquidity["flags"]


def test_repeated_identical_ohlcv_flags_manipulation_data_quality_suspicion():
    payload = _payload()
    duplicate = deepcopy(payload["market_bars"][0])
    duplicate["timestamp"] = "2026-06-21T00:00:00+07:00"
    payload["market_bars"].append(duplicate)

    result = run_risk_engine_v3(payload=payload)

    dimension = result["risk_dimensions"]["manipulation_susceptibility_risk"]
    assert dimension["risk_level"] in {"high", "critical"}
    assert "repeated_identical_ohlcv" in dimension["flags"]


def test_extreme_high_low_range_flags_volatility_gap_risk():
    payload = _payload()
    payload["market_bars"][0]["high"] = 180
    payload["market_bars"][0]["low"] = 40

    result = run_risk_engine_v3(payload=payload)

    dimension = result["risk_dimensions"]["volatility_gap_risk"]
    assert dimension["risk_level"] in {"high", "critical"}
    assert any(flag.endswith("extreme_range") for flag in dimension["flags"])


def test_stale_timestamps_flag_staleness_risk():
    payload = _payload()
    payload["market_bars"][0]["timestamp"] = "2025-01-01T00:00:00+07:00"
    payload["market_bars"][1]["timestamp"] = "2025-01-02T00:00:00+07:00"
    payload["risk_context"]["max_bar_age_days"] = 500

    result = run_risk_engine_v3(payload=payload)

    dimension = result["risk_dimensions"]["staleness_risk"]
    assert dimension["risk_level"] in {"high", "critical"}
    assert "stale_local_rows" in dimension["flags"]


def test_duplicate_timestamps_flag_ohlcv_integrity_risk():
    payload = _payload()
    payload["market_bars"][1]["timestamp"] = payload["market_bars"][0]["timestamp"]

    result = run_risk_engine_v3(payload=payload)

    dimension = result["risk_dimensions"]["ohlcv_integrity_risk"]
    assert dimension["risk_level"] in {"high", "critical"}
    assert "duplicate_timestamps" in dimension["flags"]


def test_missing_context_flags_missing_context_risk():
    payload = _payload()
    payload["scenario_context"] = {}
    payload["risk_context"] = {}

    result = run_risk_engine_v3(payload=payload)

    dimension = result["risk_dimensions"]["missing_context_risk"]
    assert dimension["risk_level"] in {"medium", "high", "critical"}
    assert any(flag.startswith("missing_") for flag in dimension["flags"])


def test_conflicting_ml_and_scenario_summary_flags_evidence_consistency_risk():
    payload = _payload()
    ml_summary = run_ml_diagnostic_engine(tuple(payload["model_diagnostics"]))
    scenario_summary = {"stability_status": "unstable", "scenario_risk_level": "high"}

    result = run_risk_engine_v3(payload=payload, ml_summary=ml_summary, scenario_summary=scenario_summary)

    dimension = result["risk_dimensions"]["evidence_consistency_risk"]
    assert dimension["risk_level"] in {"high", "critical"}
    assert "ml_scenario_consistency_conflict" in dimension["flags"]


def test_critical_risk_blocks_decision_lane_v2():
    payload = _payload()
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
    assert decision["auto_execution_allowed"] is False


def test_risk_engine_v3_outputs_no_action_labels():
    result = run_risk_engine_v3(payload=_payload())
    text = str(result).lower()

    for term in ("buy", "sell", "hold"):
        assert re.search(rf"\b{term}\b", text) is None
