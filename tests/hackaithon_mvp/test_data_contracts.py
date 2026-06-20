from datetime import datetime

import pytest

from src.hackaithon_mvp.data_contracts import (
    DEFAULT_TICKERS,
    BarRecord,
    build_timeframe_requirements,
    estimate_required_bars,
)
from src.hackaithon_mvp.timeframe_schema import REQUIRED_TIMEFRAME_INPUTS


def test_valid_bar_record_normalizes_contract_fields():
    record = BarRecord(
        ticker="VCB",
        timeframe="1 ngày",
        timestamp=datetime(2026, 6, 20, 9, 0, 0),
        open=100.0,
        high=110.0,
        low=95.0,
        close=105.0,
        volume=1000,
        source="local_sample",
        adjusted_close=104.5,
        metadata={"quality": "contract_test"},
    )

    assert record.ticker == "VCB"
    assert record.timeframe == "1d"
    assert record.timestamp.startswith("2026-06-20T09:00:00")
    assert record.volume == 1000.0


def test_bar_record_rejects_invalid_timeframe():
    with pytest.raises(ValueError, match="unsupported timeframe"):
        BarRecord(
            ticker="VCB",
            timeframe="3m",
            timestamp="2026-06-20T09:00:00",
            open=100.0,
            high=110.0,
            low=95.0,
            close=105.0,
            volume=1000,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"high": 90.0, "low": 95.0},
        {"open": 94.0, "high": 110.0, "low": 95.0},
        {"close": 111.0, "high": 110.0, "low": 95.0},
        {"volume": -1},
    ],
)
def test_bar_record_rejects_invalid_ohlc_or_volume(payload):
    values = {
        "ticker": "VCB",
        "timeframe": "1d",
        "timestamp": "2026-06-20T09:00:00",
        "open": 100.0,
        "high": 110.0,
        "low": 95.0,
        "close": 105.0,
        "volume": 1000,
    }
    values.update(payload)

    with pytest.raises(ValueError):
        BarRecord(**values)


def test_estimate_required_bars_formula():
    assert estimate_required_bars(10_000, 120, 40, 100) == 10_260


def test_default_requirements_cover_30_tickers_and_18_timeframes():
    requirements = build_timeframe_requirements(DEFAULT_TICKERS, REQUIRED_TIMEFRAME_INPUTS)

    assert len(DEFAULT_TICKERS) == 30
    assert len(REQUIRED_TIMEFRAME_INPUTS) == 18
    assert len(requirements) == 540
    assert requirements[0].required_bars == 10_221
    assert requirements[-1].required_bars == 10_260
