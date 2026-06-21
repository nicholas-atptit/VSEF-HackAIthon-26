from pathlib import Path

from src.hackaithon_mvp.llm_storage_contract import CLAIM_BOUNDARY, CREATED_AT
from src.hackaithon_mvp.local_evidence_store import (
    RECORDS_FILE_NAME,
    read_llm_readable_records,
    search_llm_readable_records,
    validate_evidence_store_root,
    write_llm_readable_records,
)


def _record(record_id: str, record_type: str = "engine_run_summary") -> dict:
    return {
        "record_id": record_id,
        "record_type": record_type,
        "title": "Diagnostic engine boundary",
        "summary": "Read-only local diagnostic evidence.",
        "content": {"topic": "diagnostic engine boundary", "human_review_required": True},
        "source_module": "test",
        "created_at": CREATED_AT,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": "Local evidence context for research diagnostics; read-only retrieval only.",
        "human_review_required": True,
        "read_only": True,
    }


def test_local_evidence_store_writes_only_with_explicit_store_root(tmp_path):
    refused = write_llm_readable_records(records=(_record("a"),), store_root="")

    assert refused["write_status"] == "refused_invalid_store_root"

    result = write_llm_readable_records(records=(_record("a"),), store_root=str(tmp_path))

    assert result["write_status"] == "written_local_jsonl"
    assert result["written_count"] == 1
    assert (tmp_path / RECORDS_FILE_NAME).exists()


def test_local_evidence_store_read_and_search_under_temp_dir(tmp_path):
    records = (
        _record("a", "engine_run_summary"),
        _record("b", "risk_assessment"),
        _record("c", "scenario_assessment"),
    )
    write_llm_readable_records(records=records, store_root=str(tmp_path))

    read_records = read_llm_readable_records(store_root=str(tmp_path))
    risk_records = read_llm_readable_records(store_root=str(tmp_path), record_type="risk_assessment")
    search_records = search_llm_readable_records(store_root=str(tmp_path), query="risk boundary", limit=2)

    assert len(read_records) == 3
    assert len(risk_records) == 1
    assert risk_records[0]["record_type"] == "risk_assessment"
    assert 1 <= len(search_records) <= 2
    assert all(record["read_only"] is True for record in read_records)


def test_validate_evidence_store_root_does_not_create_missing_path(tmp_path):
    missing = tmp_path / "not-created"

    result = validate_evidence_store_root(str(missing))

    assert result["is_valid"] is True
    assert result["store_exists"] is False
    assert not missing.exists()


def test_read_missing_store_returns_empty_tuple(tmp_path):
    missing = tmp_path / "missing-store"

    records = read_llm_readable_records(store_root=str(missing))

    assert records == tuple()


def test_invalid_record_is_not_written(tmp_path):
    invalid = _record("bad")
    invalid["human_review_required"] = False

    result = write_llm_readable_records(records=(invalid,), store_root=str(tmp_path))

    assert result["write_status"] == "refused_invalid_records"
    assert not Path(result["record_file"]).exists()
