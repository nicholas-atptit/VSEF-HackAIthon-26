import json
import subprocess
import sys

from src.hackaithon_mvp.social_listening_contract import (
    build_empty_social_context,
    get_social_listening_contract,
    validate_social_signal_record,
)


def test_social_listening_contract_is_schema_only():
    contract = get_social_listening_contract()

    assert contract["contract_status"] == "schema_contract_only"
    assert contract["runtime_boundary"]["api_calls_enabled"] is False
    assert contract["runtime_boundary"]["scraping_enabled"] is False
    assert contract["runtime_boundary"]["social_ingestion_enabled"] is False
    assert contract["runtime_boundary"]["sentiment_model_enabled"] is False
    assert contract["runtime_boundary"]["live_data_enabled"] is False


def test_empty_social_context_performs_no_ingestion_or_api_activity():
    context = build_empty_social_context()

    assert context["record_count"] == 0
    assert context["api_calls_performed"] is False
    assert context["scraping_performed"] is False
    assert context["social_ingestion_performed"] is False
    assert context["sentiment_model_used"] is False
    assert context["live_data_used"] is False


def test_social_signal_record_validation_requires_human_review():
    record = {
        "ticker": "VCB",
        "timestamp": "2026-01-01T00:00:00+07:00",
        "source_type": "manual_note",
        "signal_category": "uncertain_context",
        "sentiment_score": 0.0,
        "confidence": 0.5,
        "evidence_reference": "local-review-note",
        "human_review_required": True,
    }

    assert validate_social_signal_record(record)["is_valid"] is True
    invalid = {**record, "human_review_required": False}
    assert validate_social_signal_record(invalid)["is_valid"] is False


def test_social_listening_contract_cli_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.social_listening_contract"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout)["empty_context"]["record_count"] == 0
