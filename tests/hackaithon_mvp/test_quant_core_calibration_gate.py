from src.hackaithon_mvp.quant_core_calibration_gate import apply_calibration_gate, build_calibration_gate_policy
from src.hackaithon_mvp.quant_core_performance_attribution import build_performance_attribution


def _row(ticker, diagnostic, actual, index):
    return {
        "ticker": ticker,
        "timeframe": "1h",
        "prediction_timestamp": f"2026-01-01T{index:02d}:00:00",
        "horizon_steps": 40,
        "forecast_diagnostic": diagnostic,
        "actual_future_return": 1.0 if actual == "positive" else -1.0,
        "actual_direction_label": actual,
        "model_family": "mf",
    }


def _rows():
    rows = []
    for index in range(15):
        rows.append(_row("AAA", "positive_bias", "positive", index))
    for index in range(15, 30):
        rows.append(_row("AAA", "negative_bias", "negative", index))
    for index in range(30, 45):
        rows.append(_row("BBB", "positive_bias", "negative", index))
    for index in range(45, 60):
        rows.append(_row("BBB", "negative_bias", "positive", index))
    return tuple(rows)


def _policy():
    attribution = build_performance_attribution(_rows(), group_fields=("ticker", "timeframe", "horizon_steps", "model_family"), min_sample_count=30)
    return build_calibration_gate_policy(attribution, min_sample_count=30)


def test_calibration_gate_preserves_eligible_directional_output():
    row = {
        "ticker": "AAA",
        "timeframe": "1h",
        "horizon_steps": 40,
        "model_family": "mf",
        "forecast_diagnostic": "positive_bias",
    }

    gated = apply_calibration_gate(row, _policy())

    assert gated["forecast_diagnostic"] == "positive_bias"
    assert gated["gate_status"] == "directional_allowed"


def test_calibration_gate_downgrades_weak_directional_output():
    row = {
        "ticker": "BBB",
        "timeframe": "1h",
        "horizon_steps": 40,
        "model_family": "mf",
        "forecast_diagnostic": "positive_bias",
    }

    gated = apply_calibration_gate(row, _policy())

    assert gated["forecast_diagnostic"] == "neutral_or_uncertain"
    assert gated["gate_status"] == "downgraded_to_uncertain"
    assert gated["gate_reason"] == "weak_historical_slice"


def test_calibration_gate_never_upgrades_neutral_output():
    row = {
        "ticker": "AAA",
        "timeframe": "1h",
        "horizon_steps": 40,
        "model_family": "mf",
        "forecast_diagnostic": "neutral_or_uncertain",
    }

    gated = apply_calibration_gate(row, _policy())

    assert gated["forecast_diagnostic"] == "neutral_or_uncertain"
    assert gated["gate_status"] == "non_directional_preserved"
