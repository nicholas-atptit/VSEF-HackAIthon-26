from pathlib import Path

import pytest

from src.hackaithon_mvp.local_storage.parquet_adapter import (
    detect_parquet_capability,
    read_dataset_records,
    read_records,
    write_dataset_records,
    write_records,
)


def _records():
    return (
        {"ticker": "VCB", "timeframe": "1d", "timestamp": "2026-06-20T00:00:00+07:00", "value": 1},
        {"ticker": "VCB", "timeframe": "1d", "timestamp": "2026-06-21T00:00:00+07:00", "value": 2},
    )


def test_parquet_capability_returns_expected_fields():
    capability = detect_parquet_capability()

    assert set(capability).issuperset(
        {"pandas_available", "parquet_engine", "parquet_engine_available", "storage_format", "claim_boundary"}
    )
    assert capability["storage_format"] in {"parquet", "jsonl_fallback"}
    assert capability["claim_boundary"]["provider_calls_enabled"] is False


def test_write_and_read_records_with_parquet_or_jsonl_fallback(tmp_path):
    requested = tmp_path / "records.parquet"
    result = write_records(str(requested), _records())
    rows = read_records(str(requested))

    assert result["row_count"] == 2
    assert Path(result["actual_path"]).exists()
    assert rows == _records()


def test_fallback_path_is_reported_when_parquet_engine_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr("src.hackaithon_mvp.local_storage.parquet_adapter._find_parquet_engine", lambda: None)
    requested = tmp_path / "records.parquet"

    result = write_records(str(requested), _records())

    assert result["parquet_engine_available"] is False
    assert result["storage_format"] == "jsonl_fallback"
    assert result["actual_path"].endswith("records.jsonl")


def test_dataset_helpers_write_and_read_partitioned_records(tmp_path):
    result = write_dataset_records(
        str(tmp_path),
        "market_bars",
        _records(),
        ticker="vcb",
        timeframe="1 ngày",
        date="2026-06-20",
    )
    rows = read_dataset_records(str(tmp_path), "market_bars", ticker="VCB", timeframe="1d", date="2026-06-20")

    assert result["requested_path"].endswith("market_bars/ticker=VCB/timeframe=1d/date=2026-06-20/part.parquet")
    assert rows == _records()


def test_write_records_rejects_invalid_inputs(tmp_path):
    with pytest.raises(ValueError, match="path must be non-empty"):
        write_records("", _records())
    with pytest.raises(ValueError, match="records must be a tuple"):
        write_records(str(tmp_path / "x.parquet"), [{"a": 1}])
    with pytest.raises(ValueError, match="records must contain dictionaries"):
        write_records(str(tmp_path / "x.parquet"), ("bad",))
