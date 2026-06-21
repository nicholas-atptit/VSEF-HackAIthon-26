import json
import subprocess
import sys

from src.hackaithon_mvp.local_evidence_store import read_llm_readable_records
from src.hackaithon_mvp.offline_data_gateway import (
    build_payload_from_local_records,
    detect_local_data_format,
    normalize_market_bar_records,
    read_local_records,
    run_offline_gateway_to_engine,
    validate_market_bar_records,
)


def _rows() -> tuple[dict, ...]:
    return (
        {"ticker": "demo", "timestamp": "2026-01-01", "open": 100, "high": 105, "low": 99, "close": 102, "volume": 100000},
        {"symbol": "demo", "date": "2026-01-02", "o": 102, "h": 106, "l": 101, "c": 104, "v": 120000},
        {"ticker": "DEMO", "timestamp": "2026-01-03", "open": 104, "high": 107, "low": 103, "close": 106, "volume": 130000},
    )


def test_csv_input_is_read_and_normalized(tmp_path):
    path = tmp_path / "bars.csv"
    path.write_text(
        "\n".join(
            [
                "symbol,date,o,h,l,c,v",
                "demo,2026-01-01,100,105,99,102,100000",
                "demo,2026-01-02,102,106,101,104,120000",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = read_local_records(str(path))
    normalized = normalize_market_bar_records(records)

    assert detect_local_data_format(str(path))["format"] == "csv"
    assert len(records) == 2
    assert normalized[0]["ticker"] == "DEMO"
    assert normalized[0]["open"] == 100.0


def test_jsonl_input_is_read_and_normalized(tmp_path):
    path = tmp_path / "bars.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in _rows()) + "\n", encoding="utf-8")

    records = read_local_records(str(path))
    normalized = normalize_market_bar_records(records)

    assert detect_local_data_format(str(path))["format"] == "jsonl"
    assert len(records) == 3
    assert normalized[1]["timestamp"] == "2026-01-02"


def test_invalid_bars_fail_validation_safely():
    records = ({"ticker": "DEMO", "timestamp": "2026-01-01", "open": 100, "high": 99, "low": 98, "close": 101, "volume": 1},)

    result = validate_market_bar_records(records)

    assert result["is_valid"] is False
    assert result["records_invalid"] == 1
    assert "high" in " ".join(result["errors"]).lower()


def test_duplicate_timestamps_warn():
    records = (
        {"ticker": "DEMO", "timestamp": "2026-01-01", "open": 100, "high": 105, "low": 99, "close": 102, "volume": 100},
        {"ticker": "DEMO", "timestamp": "2026-01-01", "open": 102, "high": 106, "low": 101, "close": 104, "volume": 120},
    )

    result = validate_market_bar_records(records)

    assert result["is_valid"] is True
    assert any("duplicate timestamps" in warning for warning in result["warnings"])


def test_bad_ohlc_relation_fails_validation():
    result = validate_market_bar_records(
        (
            {
                "ticker": "DEMO",
                "timestamp": "2026-01-01",
                "open": 100,
                "high": 105,
                "low": 103,
                "close": 102,
                "volume": 100,
            },
        )
    )

    assert result["is_valid"] is False
    assert "low" in " ".join(result["errors"]).lower()


def test_normalized_payload_feeds_diagnostic_engine():
    payload = build_payload_from_local_records(records=_rows(), ticker="DEMO")
    result = run_offline_gateway_to_engine(input_path="", ticker="DEMO")

    assert payload["request"]["ticker"] == "DEMO"
    assert payload["market_bars"][0]["timeframe"] == "1d"
    assert result["gateway_status"] == "safe_failure"


def test_offline_gateway_runs_engine_and_no_write_by_default(tmp_path):
    path = tmp_path / "bars.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in _rows()) + "\n", encoding="utf-8")

    result = run_offline_gateway_to_engine(input_path=str(path), ticker="DEMO")

    assert result["gateway_status"] == "completed"
    assert result["engine_result"]["engine_status"] == "completed_gateway_ready_local_engine_core"
    assert result["store_write_status"] == "not_requested"
    assert result["llm_records_written"] == 0


def test_explicit_temp_store_root_writes_llm_evidence_records(tmp_path):
    path = tmp_path / "bars.jsonl"
    store_root = tmp_path / "store"
    path.write_text("\n".join(json.dumps(row) for row in _rows()) + "\n", encoding="utf-8")

    result = run_offline_gateway_to_engine(input_path=str(path), ticker="DEMO", store_root=str(store_root))
    records = read_llm_readable_records(store_root=str(store_root))

    assert result["store_write_status"] == "written_local_jsonl"
    assert result["llm_records_written"] == len(records)
    assert len(records) > 0
    assert all(record["read_only"] is True for record in records)


def test_offline_gateway_cli_report_exits_cleanly(tmp_path):
    path = tmp_path / "bars.csv"
    path.write_text(
        "ticker,timestamp,open,high,low,close,volume\nDEMO,2026-01-01,100,105,99,102,100000\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.offline_data_gateway",
            "--input",
            str(path),
            "--ticker",
            "DEMO",
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Offline Data Gateway v0" in completed.stdout
    assert "Gateway status: completed" in completed.stdout


def test_missing_input_path_returns_clean_error_report():
    result = run_offline_gateway_to_engine(input_path="missing.csv", ticker="DEMO")

    assert result["gateway_status"] == "safe_failure"
    assert result["errors"]
