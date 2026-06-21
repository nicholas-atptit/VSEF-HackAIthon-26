import json
import re
from pathlib import Path

from src.hackaithon_mvp.engine_universe_forecast_sweep import (
    render_engine_universe_sweep_report,
    run_engine_universe_forecast_sweep,
)
from src.hackaithon_mvp.engine_universe_sweep_readiness import (
    render_engine_universe_sweep_readiness_report,
    run_engine_universe_sweep_readiness_gate,
)


MODULES = (
    Path("src/hackaithon_mvp/engine_universe_forecast_sweep.py"),
    Path("src/hackaithon_mvp/engine_universe_sweep_readiness.py"),
    Path("tests/hackaithon_mvp/test_engine_universe_forecast_sweep.py"),
    Path("tests/hackaithon_mvp/test_engine_universe_sweep_cli.py"),
    Path("tests/hackaithon_mvp/test_engine_universe_sweep_readiness.py"),
)
CORPORATE_TERMS = (
    "".join(("v", "sef")),
    "".join(("viet", "combank")),
    "".join(("viet", "tel")),
)
RELATIONSHIP_TERMS = (
    "".join(("spon", "sor")),
    "".join(("spon", "sorship")),
    "".join(("fund", "ing")),
    "".join(("part", "ner")),
    "".join(("part", "nership")),
    "".join(("endorse", "ment")),
    "".join(("deploy", "ment")),
    "".join(("appro", "val")),
    "".join(("client ", "relationship")),
)
_SCOPE_TOKEN = "".join((chr(113), chr(109), chr(108)))
SCOPE_TERMS = (
    _SCOPE_TOKEN,
    "non-" + _SCOPE_TOKEN,
    "non" + _SCOPE_TOKEN,
)
ACTION_TERMS = (
    "".join(("b", "uy")),
    "".join(("se", "ll")),
    "".join(("ho", "ld")),
    "".join(("trading ", "signal")),
    "".join(("trade ", "recommendation")),
)
ADVICE_TERMS = (
    "".join(("financial ", "advice")),
    "".join(("investment ", "advice")),
)
OVERCLAIM_TERMS = (
    "".join(("production-", "ready")),
    "".join(("production ", "ready")),
    "".join(("guaranteed ", "profit")),
    "".join(("guaranteed ", "profitability")),
)
FORBIDDEN_TERMS = (
    *CORPORATE_TERMS,
    *RELATIONSHIP_TERMS,
    *SCOPE_TERMS,
    *ACTION_TERMS,
    *ADVICE_TERMS,
    *OVERCLAIM_TERMS,
)


def _word_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term.lower()).replace(r"\ ", r"\s+")
    if re.fullmatch(r"[a-z0-9]+", term.lower()):
        return re.compile(rf"\b{escaped}\b")
    return re.compile(escaped)


def _assert_no_forbidden_text(text: str):
    lowered = text.lower()
    for term in FORBIDDEN_TERMS:
        assert not _word_pattern(term).search(lowered), term


def test_engine_universe_sweep_new_sources_have_no_forbidden_public_terms():
    for path in MODULES:
        _assert_no_forbidden_text(path.read_text(encoding="utf-8"))


def test_engine_universe_sweep_outputs_have_no_forbidden_public_terms():
    summary = run_engine_universe_forecast_sweep(limit=25)
    readiness = run_engine_universe_sweep_readiness_gate()
    text = "\n".join(
        [
            json.dumps(summary, sort_keys=True, default=str),
            render_engine_universe_sweep_report(summary),
            json.dumps(readiness, sort_keys=True, default=str),
            render_engine_universe_sweep_readiness_report(readiness),
        ]
    )

    _assert_no_forbidden_text(text)


def test_engine_universe_sweep_outputs_keep_static_local_boundaries():
    summary = run_engine_universe_forecast_sweep(limit=10)
    flags = summary["claim_boundary_flags"]

    assert flags["research_only"] is True
    assert flags["diagnostic_only"] is True
    assert flags["baseline_ml_only"] is True
    assert flags["human_review_required"] is True
    assert flags["live_data_enabled"] is False
    assert flags["provider_calls_enabled"] is False
    assert flags["training_enabled"] is False
    assert flags["live_inference_enabled"] is False
    assert flags["benchmark_rerun"] is False
