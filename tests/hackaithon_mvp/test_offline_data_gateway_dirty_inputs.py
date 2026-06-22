import json

from src.hackaithon_mvp.local_evidence_store import read_llm_readable_records
from src.hackaithon_mvp.offline_data_gateway import (
    read_local_records,
    run_offline_gateway_to_engine,
    validate_market_bar_records,
)


def _row(**overrides):
    row = {
        "ticker": "DEMO",
        "timestamp": "2026-01-01T00:00:00+07:00",
        "open": 100,
        "high": 105,
        "low": 99,
        "close": 102,
        "volume": 1000,
    }
    row.update(overrides)
    return row


def test_csv_alias_columns_are_accepted(tmp_path):
    path = tmp_path / "bars.csv"
    path.write_text("symbol,date,o,h,l,c,v\nDEMO,2026-01-01,100,105,99,102,1000\n", encoding="utf-8")

    result = run_offline_gateway_to_engine(input_path=str(path), ticker="DEMO")

    assert result["gateway_status"] == "completed"
    assert result["normalized_records"][0]["ticker"] == "DEMO"


def test_jsonl_alias_columns_are_accepted(tmp_path):
    path = tmp_path / "bars.jsonl"
    path.write_text(json.dumps({"symbol": "demo", "date": "2026-01-01", "o": 100, "h": 105, "l": 99, "c": 102, "v": 10}), encoding="utf-8")

    result = run_offline_gateway_to_engine(input_path=str(path), ticker="DEMO")

    assert result["gateway_status"] == "completed"
    assert result["records_valid"] == 1


def test_duplicate_timestamp_warns_but_does_not_abort():
    result = validate_market_bar_records((_row(), _row(open=102, high=106, low=101, close=104)))

    assert result["is_valid"] is True
    assert any("duplicate timestamps" in warning for warning in result["warnings"])


def test_missing_close_fails_safely():
    row = _row()
    row.pop("close")
    result = validate_market_bar_records((row,))

    assert result["is_valid"] is False
    assert "missing required bar fields" in " ".join(result["errors"])


def test_high_lower_than_low_fails_safely():
    result = validate_market_bar_records((_row(high=90, low=99),))

    assert result["is_valid"] is False
    assert "high" in " ".join(result["errors"]).lower()


def test_negative_volume_fails_safely():
    result = validate_market_bar_records((_row(volume=-1),))

    assert result["is_valid"] is False
    assert "volume" in " ".join(result["errors"]).lower()


def test_mixed_ticker_rows_filter_requested_ticker(tmp_path):
    path = tmp_path / "bars.jsonl"
    rows = [_row(ticker="AAA"), _row(ticker="BBB", timestamp="2026-01-02T00:00:00+07:00")]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    result = run_offline_gateway_to_engine(input_path=str(path), ticker="BBB")

    assert result["gateway_status"] == "completed"
    assert {bar["ticker"] for bar in result["payload"]["market_bars"]} == {"BBB"}


def test_unsorted_timestamps_remain_valid(tmp_path):
    path = tmp_path / "bars.jsonl"
    rows = [_row(timestamp="2026-01-03T00:00:00+07:00"), _row(timestamp="2026-01-01T00:00:00+07:00")]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    result = run_offline_gateway_to_engine(input_path=str(path), ticker="DEMO")

    assert result["gateway_status"] == "completed"


def test_empty_file_returns_safe_failure(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    result = run_offline_gateway_to_engine(input_path=str(path), ticker="DEMO")

    assert result["gateway_status"] == "safe_failure"
    assert result["records_valid"] == 0


def test_malformed_jsonl_returns_safe_failure(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")

    result = run_offline_gateway_to_engine(input_path=str(path), ticker="DEMO")

    assert result["gateway_status"] == "safe_failure"
    assert result["errors"]


def test_provider_looking_secret_fields_rejected():
    result = validate_market_bar_records((_row(api_key="secret"),))

    assert result["is_valid"] is False
    assert "secret material" in " ".join(result["errors"])


def test_no_write_by_default_and_explicit_store_root_writes_records(tmp_path):
    path = tmp_path / "bars.jsonl"
    path.write_text(json.dumps(_row()), encoding="utf-8")

    no_write = run_offline_gateway_to_engine(input_path=str(path), ticker="DEMO")
    store_root = tmp_path / "store"
    with_write = run_offline_gateway_to_engine(input_path=str(path), ticker="DEMO", store_root=str(store_root))
    records = read_llm_readable_records(store_root=str(store_root))

    assert no_write["store_write_status"] == "not_requested"
    assert no_write["llm_records_written"] == 0
    assert with_write["store_write_status"] == "written_local_jsonl"
    assert len(records) == with_write["llm_records_written"]


def test_read_local_records_rejects_non_object_jsonl(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("[1, 2]\n", encoding="utf-8")

    try:
        read_local_records(str(path))
    except ValueError as exc:
        assert "object records" in str(exc)
    else:
        raise AssertionError("expected ValueError")
