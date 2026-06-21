from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
from src.hackaithon_mvp.diagnostic_engine_hardening_gate import run_diagnostic_engine_hardening_gate
from src.hackaithon_mvp.diagnostic_to_llm_records import (
    build_llm_records_from_diagnostic_result,
    build_llm_records_from_diagram_readiness,
    build_llm_records_from_hardening_gate,
)
from src.hackaithon_mvp.diagram_demo_readiness import build_diagram_demo_readiness_summary
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.llm_storage_contract import validate_llm_readable_record


def test_diagnostic_engine_result_converts_to_llm_readable_records():
    result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture())

    records = build_llm_records_from_diagnostic_result(result)
    record_types = {record["record_type"] for record in records}

    assert "engine_run_summary" in record_types
    assert "diagnostic_report" in record_types
    assert "ml_diagnostic_summary" in record_types
    assert "risk_assessment" in record_types
    assert "scenario_assessment" in record_types
    assert "decision_lane_output" in record_types
    assert "evidence_packet" in record_types
    assert "claim_boundary" in record_types
    assert "limitation_note" in record_types
    assert all(validate_llm_readable_record(record)["is_valid"] for record in records)
    assert all(record["read_only"] is True for record in records)


def test_hardening_gate_result_converts_to_llm_readable_records():
    records = build_llm_records_from_hardening_gate(run_diagnostic_engine_hardening_gate())
    record_types = {record["record_type"] for record in records}

    assert "hardening_gate_report" in record_types
    assert "claim_boundary" in record_types
    assert "limitation_note" in record_types
    assert all(validate_llm_readable_record(record)["is_valid"] for record in records)


def test_diagram_readiness_result_converts_to_llm_readable_records():
    records = build_llm_records_from_diagram_readiness(build_diagram_demo_readiness_summary())
    record_types = {record["record_type"] for record in records}

    assert "architecture_alignment" in record_types
    assert "diagram_coverage" in record_types
    assert "claim_boundary" in record_types
    assert "limitation_note" in record_types
    assert all(validate_llm_readable_record(record)["is_valid"] for record in records)
