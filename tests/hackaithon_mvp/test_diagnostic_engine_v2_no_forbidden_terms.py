import json
import re
from pathlib import Path

from src.hackaithon_mvp.demo_ui import build_demo_ui_summary, render_demo_ui_text
from src.hackaithon_mvp.diagnostic_engine import (
    render_diagnostic_engine_report,
    run_diagnostic_engine_from_payload,
)
from src.hackaithon_mvp.diagnostic_engine_hardening_gate import (
    render_diagnostic_engine_hardening_report,
    run_diagnostic_engine_hardening_gate,
)
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture


NEW_MODULES = (
    Path("src/hackaithon_mvp/engine_input_contract.py"),
    Path("src/hackaithon_mvp/ml_diagnostic_engine.py"),
    Path("src/hackaithon_mvp/risk_engine_v2.py"),
    Path("src/hackaithon_mvp/scenario_engine_v2.py"),
    Path("src/hackaithon_mvp/decision_lane_v2.py"),
    Path("src/hackaithon_mvp/diagnostic_engine.py"),
    Path("src/hackaithon_mvp/diagnostic_engine_hardening_gate.py"),
    Path("src/hackaithon_mvp/demo_ui.py"),
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
_ADVICE_TERMS = ("".join(("financial ", "advice")),)
_ACTION_TERMS = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))
FORBIDDEN_TEXT_PATTERNS = tuple(
    r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
    for term in (*_RELATIONSHIP_TERMS, *_SCOPE_TERMS, *_ADVICE_TERMS, *_ACTION_TERMS)
)


def _assert_no_forbidden_text(text: str):
    lowered = text.lower()
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        assert not re.search(pattern, lowered), pattern


def test_new_v2_module_source_has_no_forbidden_public_terms():
    for path in NEW_MODULES:
        _assert_no_forbidden_text(path.read_text(encoding="utf-8"))


def test_v2_outputs_have_no_forbidden_public_terms():
    engine_result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture())
    hardening_result = run_diagnostic_engine_hardening_gate()
    demo_summary = build_demo_ui_summary()
    text = "\n".join(
        [
            json.dumps(engine_result, sort_keys=True, default=str),
            render_diagnostic_engine_report(engine_result),
            json.dumps(hardening_result, sort_keys=True, default=str),
            render_diagnostic_engine_hardening_report(hardening_result),
            json.dumps(demo_summary, sort_keys=True, default=str),
            render_demo_ui_text(demo_summary),
        ]
    )

    _assert_no_forbidden_text(text)


def test_v2_outputs_keep_local_static_boundary_flags():
    result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture())

    assert result["claim_boundary"]["no_live_data"] is True
    assert result["claim_boundary"]["no_provider_calls"] is True
    assert result["claim_boundary"]["no_training"] is True
    assert result["claim_boundary"]["no_inference"] is True
    assert result["claim_boundary"]["no_benchmark_rerun"] is True
    assert result["decision_lane_v2"]["human_review_required"] is True
    assert result["decision_lane_v2"]["auto_execution_allowed"] is False
