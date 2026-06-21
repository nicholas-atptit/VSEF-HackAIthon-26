import json
import re
from pathlib import Path

from src.hackaithon_mvp.ollama_llm_experiment import (
    render_llm_experiment_report,
    run_ollama_llm_experiment,
)
from src.hackaithon_mvp.ollama_llm_readiness import (
    render_ollama_llm_readiness_report,
    run_ollama_llm_readiness_gate,
)
from src.hackaithon_mvp.qwen_ollama_smoke import render_qwen_ollama_smoke_report, run_qwen_ollama_smoke


MODULES = (
    Path("src/hackaithon_mvp/ollama_local_client.py"),
    Path("src/hackaithon_mvp/ollama_llm_experiment.py"),
    Path("src/hackaithon_mvp/qwen_ollama_smoke.py"),
    Path("src/hackaithon_mvp/ollama_llm_readiness.py"),
    Path("tests/hackaithon_mvp/test_ollama_local_client.py"),
    Path("tests/hackaithon_mvp/test_ollama_llm_experiment.py"),
    Path("tests/hackaithon_mvp/test_qwen_ollama_smoke.py"),
    Path("tests/hackaithon_mvp/test_ollama_llm_readiness.py"),
)
_SCOPE_TOKEN = "".join((chr(113), chr(109), chr(108)))
FORBIDDEN_TERMS = (
    "".join(("v", "sef")),
    "".join(("viet", "combank")),
    "".join(("viet", "tel")),
    "".join(("spon", "sor")),
    "".join(("spon", "sorship")),
    "".join(("fund", "ing")),
    "".join(("part", "ner")),
    "".join(("part", "nership")),
    "".join(("endorse", "ment")),
    "".join(("deploy", "ment")),
    "".join(("appro", "val")),
    "".join(("client ", "relationship")),
    _SCOPE_TOKEN,
    "non-" + _SCOPE_TOKEN,
    "non" + _SCOPE_TOKEN,
    "".join(("b", "uy")),
    "".join(("se", "ll")),
    "".join(("ho", "ld")),
    "".join(("trading ", "signal")),
    "".join(("trade ", "recommendation")),
    "".join(("financial ", "advice")),
    "".join(("investment ", "advice")),
    "".join(("production-", "ready")),
    "".join(("production ", "ready")),
    "".join(("guaranteed ", "profit")),
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


def test_ollama_new_sources_have_no_forbidden_public_terms():
    for path in MODULES:
        _assert_no_forbidden_text(path.read_text(encoding="utf-8"))


def test_ollama_outputs_have_no_forbidden_public_terms(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.hackaithon_mvp.ollama_llm_readiness.check_ollama_availability",
        lambda **kwargs: {"availability_status": "ollama_unavailable", "model": "qwen3.5:4b", "errors": []},
    )
    experiment = run_ollama_llm_experiment(store_root=str(tmp_path / "missing"), query="diagnostic boundary")
    smoke = run_qwen_ollama_smoke(model="qwen3.5:4b", store_root=str(tmp_path / "missing"))
    readiness = run_ollama_llm_readiness_gate(model="qwen3.5:4b")
    text = "\n".join(
        [
            json.dumps(experiment, sort_keys=True, default=str),
            render_llm_experiment_report(experiment),
            json.dumps(smoke, sort_keys=True, default=str),
            render_qwen_ollama_smoke_report(smoke),
            json.dumps(readiness, sort_keys=True, default=str),
            render_ollama_llm_readiness_report(readiness),
        ]
    )

    _assert_no_forbidden_text(text)


def test_ollama_outputs_keep_static_local_boundaries(tmp_path):
    result = run_ollama_llm_experiment(store_root=str(tmp_path / "missing"), query="diagnostic boundary")
    flags = result["claim_boundary"]

    assert flags["cloud_api_enabled"] is False
    assert flags["live_data_enabled"] is False
    assert flags["provider_calls_enabled"] is False
    assert flags["training_enabled"] is False
    assert flags["fine_tuning_enabled"] is False
    assert flags["market_prediction_inference_enabled"] is False
    assert flags["benchmark_rerun"] is False
    assert flags["mutates_policies"] is False
    assert flags["mutates_models"] is False
    assert flags["mutates_storage"] is False
    assert flags["mutates_evidence"] is False
    assert flags["mutates_decision_lanes"] is False
