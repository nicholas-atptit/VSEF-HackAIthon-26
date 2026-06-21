import json
import re
from pathlib import Path

from src.hackaithon_mvp.diagnostic_engine import run_diagnostic_engine_from_payload
from src.hackaithon_mvp.diagnostic_engine_hardening_gate import run_diagnostic_engine_hardening_gate
from src.hackaithon_mvp.diagnostic_to_llm_records import (
    build_llm_records_from_diagnostic_result,
    build_llm_records_from_hardening_gate,
)
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture
from src.hackaithon_mvp.llm_retriever import render_llm_context_report, retrieve_llm_context
from src.hackaithon_mvp.llm_storage_contract import build_llm_storage_contract
from src.hackaithon_mvp.llm_storage_readiness import (
    render_llm_storage_readiness_report,
    run_llm_storage_readiness_gate,
)
from src.hackaithon_mvp.local_evidence_store import write_llm_readable_records


NEW_MODULES = (
    Path("src/hackaithon_mvp/llm_storage_contract.py"),
    Path("src/hackaithon_mvp/local_evidence_store.py"),
    Path("src/hackaithon_mvp/diagnostic_to_llm_records.py"),
    Path("src/hackaithon_mvp/llm_retriever.py"),
    Path("src/hackaithon_mvp/llm_storage_readiness.py"),
)
_RELATIONSHIP_TERMS = (
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
_SCOPE_TERMS = ("".join(("q", "ml")), "".join(("non-", "qml")), "".join(("non", "qml")))
_ADVISORY_TERMS = (" ".join(("financial", "advice")),)
_ACTION_TERMS = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))
FORBIDDEN_TEXT_PATTERNS = tuple(
    r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
    for term in (*_RELATIONSHIP_TERMS, *_SCOPE_TERMS, *_ADVISORY_TERMS, *_ACTION_TERMS)
)


def _assert_no_forbidden_text(text: str):
    lowered = text.lower()
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        assert not re.search(pattern, lowered), pattern


def test_llm_storage_module_source_has_no_forbidden_public_terms():
    for path in NEW_MODULES:
        _assert_no_forbidden_text(path.read_text(encoding="utf-8"))


def test_llm_storage_outputs_have_no_forbidden_public_terms(tmp_path):
    diagnostic_result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture())
    diagnostic_records = build_llm_records_from_diagnostic_result(diagnostic_result)
    hardening_records = build_llm_records_from_hardening_gate(run_diagnostic_engine_hardening_gate())
    write_llm_readable_records(records=diagnostic_records + hardening_records, store_root=str(tmp_path))
    context = retrieve_llm_context(store_root=str(tmp_path), query="diagnostic engine boundary")
    readiness = run_llm_storage_readiness_gate()
    text = "\n".join(
        [
            json.dumps(build_llm_storage_contract(), sort_keys=True, default=str),
            json.dumps(diagnostic_records, sort_keys=True, default=str),
            json.dumps(hardening_records, sort_keys=True, default=str),
            json.dumps(context, sort_keys=True, default=str),
            render_llm_context_report(context),
            json.dumps(readiness, sort_keys=True, default=str),
            render_llm_storage_readiness_report(readiness),
        ]
    )

    _assert_no_forbidden_text(text)


def test_llm_storage_outputs_keep_local_read_only_boundaries():
    contract = build_llm_storage_contract()
    readiness = run_llm_storage_readiness_gate()

    assert contract["claim_boundary"]["read_only"] is True
    assert contract["claim_boundary"]["no_server_database"] is True
    assert contract["claim_boundary"]["no_vector_database"] is True
    assert contract["claim_boundary"]["no_live_data"] is True
    assert contract["claim_boundary"]["no_provider_calls"] is True
    assert contract["claim_boundary"]["no_training"] is True
    assert contract["claim_boundary"]["no_inference"] is True
    assert contract["claim_boundary"]["no_benchmark_rerun"] is True
    assert readiness["read_only"] is True
    assert readiness["human_review_required"] is True
