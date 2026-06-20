from src.hackaithon_mvp.actual_outcome_builder import build_actual_outcomes


def _forecast(timestamp, horizon=1):
    return {
        "ticker": "VCB",
        "timeframe": "1d",
        "prediction_timestamp": timestamp,
        "horizon_steps": horizon,
        "forecast_diagnostic": "positive_bias",
    }


def _bar(timestamp, close):
    return {
        "ticker": "VCB",
        "timeframe": "1d",
        "timestamp": timestamp,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 100,
    }


BARS = (
    _bar("2026-01-01T00:00:00+07:00", 10),
    _bar("2026-01-02T00:00:00+07:00", 11),
    _bar("2026-01-03T00:00:00+07:00", 12),
)


def test_exact_matching_works():
    rows = build_actual_outcomes((_forecast("2026-01-01T00:00:00+07:00"),), BARS, match_mode="exact")

    assert len(rows) == 1
    assert rows[0]["actual_timestamp"] == "2026-01-02T00:00:00+07:00"


def test_nearest_prior_matching_works():
    rows = build_actual_outcomes((_forecast("2026-01-02T12:00:00+07:00"),), BARS, match_mode="nearest_prior")

    assert len(rows) == 1
    assert rows[0]["actual_timestamp"] == "2026-01-03T00:00:00+07:00"


def test_nearest_prior_never_uses_future_bar_as_current():
    rows = build_actual_outcomes((_forecast("2025-12-31T12:00:00+07:00"),), BARS, match_mode="nearest_prior")

    assert rows == ()


def test_missing_current_bar_is_skipped():
    rows = build_actual_outcomes((_forecast("2026-01-01T12:00:00+07:00"),), BARS, match_mode="exact")

    assert rows == ()


def test_missing_future_bar_is_skipped():
    rows = build_actual_outcomes((_forecast("2026-01-03T00:00:00+07:00"),), BARS, match_mode="exact")

    assert rows == ()
