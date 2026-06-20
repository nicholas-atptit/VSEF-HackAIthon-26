import json
import re

from src.hackaithon_mvp.quant_core_calibration import build_score_calibration_report
from src.hackaithon_mvp.quant_core_calibration_gate import apply_calibration_gate, build_calibration_gate_policy
from src.hackaithon_mvp.quant_core_performance_attribution import build_performance_attribution
from src.hackaithon_mvp.quant_core_selector_summary import build_selector_summary


FORBIDDEN_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\bfinancial advice\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bsupport(?:ed|s|ing)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bdeployment\b",
    r"\bapproval\b",
    r"\bclient relationship\b",
)


def _assert_no_forbidden_terms(payload) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, text) is None, pattern


def _row(index, diagnostic="positive_bias", actual="positive"):
    return {
        "ticker": "AAA",
        "timeframe": "1h",
        "prediction_timestamp": f"2026-01-01T{index:02d}:00:00",
        "horizon_steps": 40,
        "forecast_diagnostic": diagnostic,
        "actual_future_return": 1.0 if actual == "positive" else -1.0,
        "actual_direction_label": actual,
        "model_family": "mf",
        "diagnostic_score": index / 100,
        "confidence": index / 100,
    }


def test_quant_core_calibration_outputs_have_no_forbidden_public_terms():
    rows = tuple(_row(index) for index in range(30))
    attribution = build_performance_attribution(rows)
    policy = build_calibration_gate_policy(attribution)
    gated = apply_calibration_gate(
        {
            "ticker": "AAA",
            "timeframe": "1h",
            "horizon_steps": 40,
            "model_family": "mf",
            "forecast_diagnostic": "positive_bias",
        },
        policy,
    )
    payload = {
        "attribution": attribution,
        "score_calibration": build_score_calibration_report(rows),
        "selector_summary": build_selector_summary(rows),
        "gated": gated,
    }

    _assert_no_forbidden_terms(payload)


def test_quant_core_modules_do_not_expose_forbidden_runtime_behavior_flags():
    rows = tuple(_row(index) for index in range(30))
    attribution = build_performance_attribution(rows)

    assert attribution["claim_boundary"]["no_live_data"] is True
    assert attribution["claim_boundary"]["no_provider_api_calls"] is True
    assert attribution["claim_boundary"]["no_training"] is True
    assert attribution["claim_boundary"]["no_inference"] is True
    assert attribution["claim_boundary"]["no_benchmark_rerun"] is True
