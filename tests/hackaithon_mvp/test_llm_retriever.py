from src.hackaithon_mvp.llm_retriever import (
    render_llm_context_report,
    retrieve_llm_context,
    validate_llm_context,
)
from src.hackaithon_mvp.llm_storage_contract import CLAIM_BOUNDARY, CREATED_AT
from src.hackaithon_mvp.local_evidence_store import write_llm_readable_records


def _record(record_id: str, record_type: str = "engine_run_summary") -> dict:
    return {
        "record_id": record_id,
        "record_type": record_type,
        "title": "Diagnostic engine boundary",
        "summary": "Read-only diagnostic engine boundary record.",
        "content": {"topic": "diagnostic engine boundary", "detail": record_type},
        "source_module": "test",
        "created_at": CREATED_AT,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": "Local evidence context for research diagnostics; read-only retrieval only.",
        "human_review_required": True,
        "read_only": True,
    }


def test_retriever_returns_read_only_context(tmp_path):
    write_llm_readable_records(
        records=(_record("a", "engine_run_summary"), _record("b", "risk_assessment")),
        store_root=str(tmp_path),
    )

    context = retrieve_llm_context(store_root=str(tmp_path), query="risk boundary", limit=5)

    assert context["retrieval_status"] == "records_available"
    assert context["record_count"] >= 1
    assert context["read_only"] is True
    assert context["human_review_required"] is True
    assert validate_llm_context(context)["is_valid"] is True


def test_retriever_handles_missing_store_cleanly(tmp_path):
    missing = tmp_path / "missing"

    context = retrieve_llm_context(store_root=str(missing), query="diagnostic engine boundary")
    report = render_llm_context_report(context)

    assert context["retrieval_status"] == "no_records_available"
    assert context["record_count"] == 0
    assert context["records"] == tuple()
    assert validate_llm_context(context)["is_valid"] is True
    assert "No records are available" in report


def test_retriever_filters_by_record_type(tmp_path):
    write_llm_readable_records(
        records=(_record("a", "engine_run_summary"), _record("b", "decision_lane_output")),
        store_root=str(tmp_path),
    )

    context = retrieve_llm_context(
        store_root=str(tmp_path),
        query="diagnostic boundary",
        record_type="decision_lane_output",
    )

    assert context["record_count"] == 1
    assert context["records"][0]["record_type"] == "decision_lane_output"
    assert "mutate policies" in context["llm_must_not"]
