from src.hackaithon_mvp.llm_storage_contract import (
    CLAIM_BOUNDARY,
    CREATED_AT,
    build_llm_storage_contract,
    build_llm_storage_manifest,
    get_llm_readable_record_types,
    validate_llm_readable_record,
)


REQUIRED_TYPES = {
    "engine_run_summary",
    "diagnostic_report",
    "evidence_packet",
    "risk_assessment",
    "scenario_assessment",
    "decision_lane_output",
    "ml_diagnostic_summary",
    "architecture_alignment",
    "diagram_coverage",
    "hardening_gate_report",
    "claim_boundary",
    "limitation_note",
}


def _record(record_type: str = "engine_run_summary") -> dict:
    return {
        "record_id": f"test:{record_type}",
        "record_type": record_type,
        "title": "Local diagnostic evidence",
        "summary": "Read-only local diagnostic evidence for reviewer context.",
        "content": {"status": "available", "human_review_required": True},
        "source_module": "test",
        "created_at": CREATED_AT,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": "Local evidence context for research diagnostics; read-only retrieval only.",
        "human_review_required": True,
        "read_only": True,
    }


def test_all_required_llm_readable_record_types_exist():
    contract = build_llm_storage_contract()

    assert set(get_llm_readable_record_types()) == REQUIRED_TYPES
    assert set(contract["record_types"]) == REQUIRED_TYPES
    assert contract["storage_format"] == "jsonl"
    assert contract["rules"]["read_only_for_llm"] is True


def test_valid_llm_readable_record_passes_validation():
    result = validate_llm_readable_record(_record("risk_assessment"))

    assert result["is_valid"] is True
    assert result["normalized_record"]["record_type"] == "risk_assessment"
    assert result["normalized_record"]["read_only"] is True
    assert result["normalized_record"]["human_review_required"] is True


def test_llm_readable_record_rejects_mutable_or_forbidden_content():
    record = _record("decision_lane_output")
    record["read_only"] = False
    record["content"]["label"] = "".join(("B", "UY"))
    record["content"]["note"] = " ".join(("financial", "advice"))

    result = validate_llm_readable_record(record)

    assert result["is_valid"] is False
    text = " ".join(result["errors"]).lower()
    assert "read_only" in text
    assert "action labels" in text
    assert "advisory" in text


def test_llm_storage_manifest_is_read_only_local_jsonl():
    manifest = build_llm_storage_manifest()

    assert manifest["manifest_status"] == "ready_for_local_llm_readable_evidence_store"
    assert manifest["storage_backends"] == ["local_jsonl"]
    assert manifest["default_write_enabled"] is False
    assert manifest["read_only_retrieval"] is True
