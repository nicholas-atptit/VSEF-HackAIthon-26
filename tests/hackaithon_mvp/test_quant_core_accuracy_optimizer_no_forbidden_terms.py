import json
import re

from src.hackaithon_mvp.quant_core_accuracy_optimizer import run_accuracy_optimization


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
    }


def test_accuracy_optimizer_output_has_no_forbidden_public_terms():
    rows = tuple(_row(index) for index in range(40))

    payload = run_accuracy_optimization(rows, calibration_ratio=0.5)
    text = json.dumps(payload, sort_keys=True).lower()

    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, text) is None, pattern


def test_accuracy_optimizer_claim_boundary_blocks_forbidden_runtime_behaviors():
    payload = run_accuracy_optimization(tuple(_row(index) for index in range(40)), calibration_ratio=0.5)

    assert payload["claim_boundary"]["no_live_data"] is True
    assert payload["claim_boundary"]["no_provider_api_calls"] is True
    assert payload["claim_boundary"]["no_training"] is True
    assert payload["claim_boundary"]["no_inference"] is True
    assert payload["claim_boundary"]["no_benchmark_rerun"] is True
