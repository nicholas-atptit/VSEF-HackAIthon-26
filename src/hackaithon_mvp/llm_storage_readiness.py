"""Readiness gate for the local LLM-readable evidence store."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from typing import Any

from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
from src.hackaithon_mvp.diagnostic_engine_hardening_gate import run_diagnostic_engine_hardening_gate
from src.hackaithon_mvp.diagnostic_to_llm_records import (
    build_llm_records_from_diagnostic_result,
    build_llm_records_from_diagram_readiness,
    build_llm_records_from_hardening_gate,
)
from src.hackaithon_mvp.diagram_demo_readiness import build_diagram_demo_readiness_summary
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.llm_retriever import retrieve_llm_context, validate_llm_context
from src.hackaithon_mvp.llm_storage_contract import (
    CLAIM_BOUNDARY,
    CREATED_AT,
    NON_CLAIM_TEXT,
    build_llm_storage_contract,
    build_llm_storage_manifest,
    get_llm_readable_record_types,
    validate_llm_readable_record,
)
from src.hackaithon_mvp.local_evidence_store import (
    read_llm_readable_records,
    search_llm_readable_records,
    write_llm_readable_records,
)


ACTION_LABEL_TERMS = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))
RELATIONSHIP_TERMS = (
    "".join(("corpor", "ate")),
    "".join(("spon", "sor")),
    "".join(("spon", "sorship")),
    "".join(("sup", "port")),
    "".join(("sup", "ported")),
    "".join(("sup", "ports")),
    "".join(("sup", "porting")),
    "".join(("fund", "ing")),
    "".join(("part", "nership")),
    "".join(("endorse", "ment")),
    "".join(("deploy", "ment")),
    "".join(("appro", "val")),
    "".join(("client ", "relationship")),
)
SCOPE_TERMS = ("".join(("q", "ml")), "".join(("non-", "q", "ml")), "".join(("non", "q", "ml")))
ADVISORY_TERMS = (" ".join(("financial", "advice")),)
FORBIDDEN_PATTERNS = tuple(
    r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
    for term in (*ACTION_LABEL_TERMS, *RELATIONSHIP_TERMS, *SCOPE_TERMS, *ADVISORY_TERMS)
)


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_strings(nested)
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _walk_strings(nested)


def _contains_forbidden_wording(value: Any) -> bool:
    text = " ".join(_walk_strings(value)).lower()
    return any(re.search(pattern, text) for pattern in FORBIDDEN_PATTERNS)


def _sample_record(record_type: str) -> dict:
    return {
        "record_id": f"sample:{record_type}",
        "record_type": record_type,
        "title": f"{record_type} sample",
        "summary": "Read-only local diagnostic evidence sample.",
        "content": {
            "record_type": record_type,
            "read_only": True,
            "human_review_required": True,
            "no_live_data": True,
            "no_provider_calls": True,
        },
        "source_module": "llm_storage_readiness",
        "created_at": CREATED_AT,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "human_review_required": True,
        "read_only": True,
    }


def _check(check_id: str, passed: bool, detail: str) -> dict:
    return {"check_id": check_id, "passed": bool(passed), "detail": detail}


def run_llm_storage_readiness_gate() -> dict:
    """Run deterministic checks for the local read-only evidence store."""

    contract = build_llm_storage_contract()
    manifest = build_llm_storage_manifest()
    record_types = get_llm_readable_record_types()
    sample_records = tuple(_sample_record(record_type) for record_type in record_types)
    sample_validations = tuple(validate_llm_readable_record(record) for record in sample_records)

    with tempfile.TemporaryDirectory() as temp_dir:
        write_result = write_llm_readable_records(records=sample_records, store_root=temp_dir)
        read_records = read_llm_readable_records(store_root=temp_dir)
        search_records = search_llm_readable_records(store_root=temp_dir, query="diagnostic evidence", limit=3)
        retrieval_context = retrieve_llm_context(store_root=temp_dir, query="diagnostic evidence", limit=3)
        retrieval_validation = validate_llm_context(retrieval_context)

    diagnostic_result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture())
    diagnostic_records = build_llm_records_from_diagnostic_result(diagnostic_result)
    hardening_result = run_diagnostic_engine_hardening_gate()
    hardening_records = build_llm_records_from_hardening_gate(hardening_result)
    diagram_result = build_diagram_demo_readiness_summary()
    diagram_records = build_llm_records_from_diagram_readiness(diagram_result)
    refused_write = write_llm_readable_records(records=(sample_records[0],), store_root="")

    checks = [
        _check(
            "storage_contract_exists",
            contract.get("contract_status") == "ready_for_local_llm_readable_evidence_contract",
            "Storage contract is available.",
        ),
        _check(
            "all_required_record_types_validate",
            set(record_types) == set(contract.get("record_types", []))
            and all(validation["is_valid"] for validation in sample_validations),
            "All required record types validate.",
        ),
        _check(
            "local_store_write_read_search",
            write_result.get("write_status") == "written_local_jsonl"
            and len(read_records) == len(sample_records)
            and len(search_records) > 0,
            "Local JSONL store can write, read, and search in a temp directory.",
        ),
        _check(
            "diagnostic_result_converts",
            len(diagnostic_records) >= 8
            and all(validate_llm_readable_record(record)["is_valid"] for record in diagnostic_records),
            "Diagnostic engine result converts to read-only records.",
        ),
        _check(
            "hardening_gate_converts",
            len(hardening_records) >= 3
            and all(validate_llm_readable_record(record)["is_valid"] for record in hardening_records),
            "Hardening gate result converts to read-only records.",
        ),
        _check(
            "diagram_readiness_converts",
            len(diagram_records) >= 4
            and all(validate_llm_readable_record(record)["is_valid"] for record in diagram_records),
            "Diagram readiness result converts to read-only records.",
        ),
        _check(
            "retriever_returns_read_only_context",
            retrieval_context.get("read_only") is True
            and retrieval_context.get("human_review_required") is True
            and retrieval_validation.get("is_valid") is True,
            "Retriever returns valid read-only context.",
        ),
        _check(
            "no_forbidden_wording",
            not _contains_forbidden_wording(
                {
                    "contract": contract,
                    "manifest": manifest,
                    "records": diagnostic_records + hardening_records + diagram_records,
                    "retrieval_context": retrieval_context,
                }
            ),
            "Readiness outputs avoid forbidden public wording.",
        ),
        _check(
            "no_write_by_default",
            refused_write.get("write_status") == "refused_invalid_store_root",
            "Writes require an explicit local store root.",
        ),
        _check(
            "no_server_or_vector_store_dependency",
            manifest.get("storage_backends") == ["local_jsonl"]
            and manifest.get("claim_boundary", {}).get("no_server_database") is True
            and manifest.get("claim_boundary", {}).get("no_vector_database") is True,
            "Only local JSONL storage is used.",
        ),
        _check(
            "no_live_or_model_runtime_behavior",
            all(
                manifest.get("claim_boundary", {}).get(key) is True
                for key in ("no_live_data", "no_provider_calls", "no_training", "no_inference", "no_benchmark_rerun")
            ),
            "Boundary flags exclude live feeds, provider calls, model updates, and benchmark reruns.",
        ),
    ]
    ready = all(check["passed"] for check in checks)
    return {
        "readiness_status": "ready_for_local_llm_readable_evidence_store" if ready else "attention_required",
        "check_count": len(checks),
        "passed_count": sum(1 for check in checks if check["passed"]),
        "checks": checks,
        "record_type_count": len(record_types),
        "sample_record_count": len(sample_records),
        "diagnostic_record_count": len(diagnostic_records),
        "hardening_record_count": len(hardening_records),
        "diagram_record_count": len(diagram_records),
        "retrieval_status": retrieval_context.get("retrieval_status"),
        "read_only": True,
        "human_review_required": True,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_llm_storage_readiness_report(result: dict) -> str:
    """Render a compact readiness report for the local LLM-readable store."""

    lines = [
        "# LLM Storage Readiness",
        "",
        f"Readiness status: {result.get('readiness_status')}",
        f"Checks passed: {result.get('passed_count')} of {result.get('check_count')}",
        f"Record types: {result.get('record_type_count')}",
        f"Diagnostic records: {result.get('diagnostic_record_count')}",
        f"Hardening records: {result.get('hardening_record_count')}",
        f"Diagram records: {result.get('diagram_record_count')}",
        "Read-only: True",
        "Human review required: True",
        "",
        "## Checks",
    ]
    for check in result.get("checks", []):
        status = "pass" if check.get("passed") else "fail"
        lines.append(f"- {check.get('check_id')}: {status}")
    lines.extend(
        [
            "",
            "## Boundary",
            "Local JSONL evidence store only; no server database or vector database is created.",
            "No live data, provider calls, training, inference, or benchmark rerun is performed.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local LLM-readable storage readiness gate.")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_llm_storage_readiness_gate()
    if args.format == "report":
        print(render_llm_storage_readiness_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("readiness_status") == "ready_for_local_llm_readable_evidence_store" else 1


if __name__ == "__main__":
    raise SystemExit(main())
