from src.hackaithon_mvp.local_storage.parquet_adapter import validate_market_bar_records


def _valid_bar(**overrides):
    record = {
        "ticker": "VCB",
        "timeframe": "1 ngày",
        "timestamp": "2026-06-20T00:00:00+07:00",
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 1000.0,
    }
    record.update(overrides)
    return record


def test_market_bar_validation_accepts_valid_records():
    validation = validate_market_bar_records((_valid_bar(),))

    assert validation["is_valid"] is True
    assert validation["row_count"] == 1
    assert validation["errors"] == []


def test_market_bar_validation_rejects_missing_fields():
    record = _valid_bar()
    record.pop("close")

    validation = validate_market_bar_records((record,))

    assert validation["is_valid"] is False
    assert "missing required fields" in validation["errors"][0]


def test_market_bar_validation_rejects_invalid_ohlcv():
    validation = validate_market_bar_records((_valid_bar(high=98.0), _valid_bar(volume=-1)))

    assert validation["is_valid"] is False
    assert any("high must be greater than or equal to low" in error for error in validation["errors"])
    assert any("volume must be non-negative" in error for error in validation["errors"])


def test_market_bar_validation_requires_tuple_records():
    validation = validate_market_bar_records([_valid_bar()])

    assert validation["is_valid"] is False
    assert validation["errors"] == ["records must be a tuple"]
