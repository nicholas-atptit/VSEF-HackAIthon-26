import pytest

from src.hackaithon_mvp.timeframe_schema import (
    CANONICAL_TIMEFRAMES,
    REQUIRED_TIMEFRAME_INPUTS,
    TIMEFRAME_ALIASES,
    assert_supported_timeframe,
    is_daily_timeframe,
    is_intraday_timeframe,
    normalize_timeframe,
    timeframe_to_horizon_steps,
    timeframe_unit,
)


REQUIRED_MAPPING = {
    "1p": "1m",
    "2p": "2m",
    "5p": "5m",
    "10p": "10m",
    "1h": "1h",
    "2h": "2h",
    "5h": "5h",
    "10h": "10h",
    "1 ngày": "1d",
    "2 ngày": "2d",
    "3 ngày": "3d",
    "4 ngày": "4d",
    "5 ngày": "5d",
    "10 ngày": "10d",
    "15 ngày": "15d",
    "20 ngày": "20d",
    "30 ngày": "30d",
    "40 ngày": "40d",
}


def test_every_required_user_facing_input_normalizes_to_canonical_value():
    assert tuple(REQUIRED_MAPPING) == REQUIRED_TIMEFRAME_INPUTS
    for value, expected in REQUIRED_MAPPING.items():
        assert normalize_timeframe(value) == expected


def test_every_canonical_value_is_supported():
    for value in CANONICAL_TIMEFRAMES:
        assert normalize_timeframe(value) == value
        assert_supported_timeframe(value)


def test_required_interval_groups_are_complete():
    assert {"1m", "2m", "5m", "10m"}.issubset(CANONICAL_TIMEFRAMES)
    assert {"1h", "2h", "5h", "10h"}.issubset(CANONICAL_TIMEFRAMES)
    assert {"1d", "2d", "3d", "4d", "5d", "10d", "15d", "20d", "30d", "40d"}.issubset(
        CANONICAL_TIMEFRAMES
    )


def test_required_aliases_are_supported():
    aliases = {
        "1 phút": "1m",
        "1min": "1m",
        "1minute": "1m",
        "10 phút": "10m",
        "10min": "10m",
        "10minute": "10m",
        "1 day": "1d",
        "1day": "1d",
        "40 day": "40d",
        "40day": "40d",
    }
    for alias, expected in aliases.items():
        assert TIMEFRAME_ALIASES[alias] == expected
        assert normalize_timeframe(alias) == expected


@pytest.mark.parametrize("value", ["3m", "15m", "30m", "6h", "7d", "", "random text"])
def test_unsupported_values_are_rejected(value):
    with pytest.raises(ValueError, match="unsupported timeframe"):
        normalize_timeframe(value)


@pytest.mark.parametrize(
    ("value", "expected_unit"),
    [
        ("1m", "minute"),
        ("10m", "minute"),
        ("1h", "hour"),
        ("10h", "hour"),
        ("1d", "day"),
        ("40d", "day"),
    ],
)
def test_timeframe_unit_returns_supported_unit(value, expected_unit):
    assert timeframe_unit(value) == expected_unit


@pytest.mark.parametrize(
    ("value", "expected_steps"),
    [
        ("1m", 1),
        ("10m", 10),
        ("2h", 2),
        ("40d", 40),
    ],
)
def test_timeframe_to_horizon_steps_returns_numeric_part(value, expected_steps):
    assert timeframe_to_horizon_steps(value) == expected_steps


def test_intraday_and_daily_helpers_classify_supported_timeframes():
    assert is_intraday_timeframe("1p") is True
    assert is_intraday_timeframe("10h") is True
    assert is_intraday_timeframe("1 ngày") is False
    assert is_daily_timeframe("1 ngày") is True
    assert is_daily_timeframe("10h") is False
