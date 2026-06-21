import json
import re
from pathlib import Path

from src.hackaithon_mvp.dag_backtest_harness import (
    build_dag_backtest_fixture,
    render_dag_backtest_report,
    run_dag_backtest_from_payloads,
)
from src.hackaithon_mvp.fine_tune_control_plane import (
    assess_fine_tune_readiness,
    build_fine_tune_experiment_candidate,
    render_fine_tune_control_report,
)
from src.hackaithon_mvp.gateway_backtest_readiness import (
    render_gateway_backtest_readiness_report,
    run_gateway_backtest_readiness_gate,
)
from src.hackaithon_mvp.offline_data_gateway import render_offline_gateway_report, run_offline_gateway_to_engine
from src.hackaithon_mvp.risk_engine_v3 import run_risk_engine_v3


NEW_MODULES = (
    Path("src/hackaithon_mvp/offline_data_gateway.py"),
    Path("src/hackaithon_mvp/local_cache_gateway.py"),
    Path("src/hackaithon_mvp/dag_backtest_harness.py"),
    Path("src/hackaithon_mvp/risk_engine_v3.py"),
    Path("src/hackaithon_mvp/fine_tune_control_plane.py"),
    Path("src/hackaithon_mvp/gateway_backtest_readiness.py"),
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
_SCOPE_TERMS = ("".join(("q", "ml")), "".join(("non-", "q", "ml")), "".join(("non", "q", "ml")))
_ADVISORY_TERMS = (" ".join(("financial", "advice")),)
_ACTION_TERMS = (
    "".join(("b", "uy")),
    "".join(("se", "ll")),
    "".join(("ho", "ld")),
)
FORBIDDEN_TEXT_PATTERNS = tuple(
    r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
    for term in (*_RELATIONSHIP_TERMS, *_SCOPE_TERMS, *_ADVISORY_TERMS, *_ACTION_TERMS)
)


def _assert_no_forbidden_text(text: str):
    lowered = text.lower()
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        assert not re.search(pattern, lowered), pattern


def test_gateway_backtest_module_source_has_no_forbidden_public_terms():
    for path in NEW_MODULES:
        _assert_no_forbidden_text(path.read_text(encoding="utf-8"))


def test_gateway_backtest_outputs_have_no_forbidden_public_terms(tmp_path):
    csv_path = tmp_path / "bars.csv"
    csv_path.write_text(
        "ticker,timestamp,open,high,low,close,volume\nDEMO,2026-01-01,100,105,99,102,100000\nDEMO,2026-01-02,102,106,101,104,120000\n",
        encoding="utf-8",
    )
    gateway = run_offline_gateway_to_engine(input_path=str(csv_path), ticker="DEMO")
    backtest = run_dag_backtest_from_payloads(payloads=tuple(build_dag_backtest_fixture()["payloads"]))
    risk = run_risk_engine_v3(payload=gateway["payload"])
    readiness = assess_fine_tune_readiness(
        engine_result=gateway["engine_result"],
        backtest_result=backtest,
        ml_summary=gateway["engine_result"]["ml_engine"],
    )
    candidate = build_fine_tune_experiment_candidate(readiness=readiness)
    gate = run_gateway_backtest_readiness_gate()
    text = "\n".join(
        [
            json.dumps(gateway, sort_keys=True, default=str),
            render_offline_gateway_report(gateway),
            json.dumps(backtest, sort_keys=True, default=str),
            render_dag_backtest_report(backtest),
            json.dumps(risk, sort_keys=True, default=str),
            json.dumps(candidate, sort_keys=True, default=str),
            render_fine_tune_control_report(readiness, candidate),
            json.dumps(gate, sort_keys=True, default=str),
            render_gateway_backtest_readiness_report(gate),
        ]
    )

    _assert_no_forbidden_text(text)


def test_gateway_backtest_outputs_keep_runtime_boundaries():
    result = run_gateway_backtest_readiness_gate()

    assert result["claim_boundary"]["no_live_data"] is True
    assert result["claim_boundary"]["no_provider_calls"] is True
    assert result["claim_boundary"]["no_training"] is True
    assert result["claim_boundary"]["no_inference"] is True
    assert result["claim_boundary"]["no_benchmark_rerun"] is True
    assert result["auto_execution_allowed"] is False
    assert result["auto_training_allowed"] is False
