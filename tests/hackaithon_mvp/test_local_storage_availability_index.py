from src.hackaithon_mvp.data_contracts import build_timeframe_requirements
from src.hackaithon_mvp.local_storage.availability_index import (
    build_availability_index,
    check_storage_readiness_against_requirements,
)


def _records():
    return (
        {"ticker": "vcb", "timeframe": "1 ngày", "timestamp": "2026-06-18T00:00:00+07:00"},
        {"ticker": "VCB", "timeframe": "1d", "timestamp": "2026-06-19T00:00:00+07:00"},
        {"ticker": "BID", "timeframe": "1d", "timestamp": "2026-06-19T00:00:00+07:00"},
    )


def test_availability_index_groups_ticker_timeframe():
    index = build_availability_index(_records())

    assert index["group_count"] == 2
    assert index["total_records"] == 3
    assert index["groups"][0]["ticker"] == "BID"
    assert index["groups"][1]["ticker"] == "VCB"
    assert index["groups"][1]["bar_count"] == 2
    assert index["groups"][1]["min_timestamp"] == "2026-06-18T00:00:00+07:00"
    assert index["groups"][1]["max_timestamp"] == "2026-06-19T00:00:00+07:00"


def test_readiness_check_reports_coverage_for_dict_requirements():
    index = build_availability_index(_records())
    requirements = (
        {"ticker": "VCB", "timeframe": "1d", "required_bars": 2},
        {"ticker": "BID", "timeframe": "1d", "required_bars": 2},
    )

    readiness = check_storage_readiness_against_requirements(index, requirements)

    assert readiness["requirements_count"] == 2
    assert readiness["ready_count"] == 1
    assert readiness["missing_count"] == 1
    assert readiness["coverage_ratio"] == 0.5
    assert readiness["missing_sample"][0]["ticker"] == "BID"


def test_readiness_check_accepts_existing_requirement_dataclasses():
    index = build_availability_index(_records())
    requirements = build_timeframe_requirements(("VCB",), ("1 ngày",), cases_per_pair=1, lookback_bars=0, safety_margin_bars=0)

    readiness = check_storage_readiness_against_requirements(index, requirements)

    assert readiness["requirements_count"] == 1
    assert readiness["ready_count"] == 1
    assert readiness["coverage_ratio"] == 1
