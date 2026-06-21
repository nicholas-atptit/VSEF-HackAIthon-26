import subprocess
import sys

from src.hackaithon_mvp import ollama_llm_readiness as readiness


def _availability(status: str) -> dict:
    return {
        "availability_status": status,
        "model": "qwen3.5:4b",
        "base_url": "http://127.0.0.1:11434",
        "available_models": [],
        "errors": [],
        "message": status,
    }


def _experiment(status: str) -> dict:
    return {
        "experiment_status": status,
        "model": "qwen3.5:4b",
        "query": "diagnostic boundary",
        "retrieval_status": "records_available" if status != "no_records_available" else "no_records_available",
        "retrieved_record_count": 1 if status != "no_records_available" else 0,
        "llm_called": status == "completed",
        "answer": "Local retrieved evidence says human review is required.",
        "source_ids": ["source-1"] if status != "no_records_available" else [],
        "abstained": status != "completed",
        "human_review_required": True,
        "read_only": True,
        "claim_boundary": {
            "cloud_api_enabled": False,
            "live_data_enabled": False,
            "provider_calls_enabled": False,
            "training_enabled": False,
            "fine_tuning_enabled": False,
            "market_prediction_inference_enabled": False,
            "benchmark_rerun": False,
            "mutates_policies": False,
            "mutates_models": False,
            "mutates_storage": False,
            "mutates_evidence": False,
            "mutates_decision_lanes": False,
        },
        "non_claim": "Local evidence-grounded LLM experiment; answers are limited to retrieved records and require human review.",
        "llm_must_not": [],
        "warnings": [],
        "errors": [],
    }


def test_ollama_llm_readiness_model_unavailable_passes(monkeypatch):
    monkeypatch.setattr(readiness, "check_ollama_availability", lambda **kwargs: _availability("model_unavailable"))
    monkeypatch.setattr(readiness, "run_ollama_llm_experiment", lambda **kwargs: _experiment("no_records_available"))
    monkeypatch.setattr(
        readiness,
        "run_qwen_ollama_smoke",
        lambda **kwargs: {"created_temp_store": True, "smoke_status": "model_unavailable", "experiment": _experiment("model_unavailable")},
    )

    result = readiness.run_ollama_llm_readiness_gate(model="qwen3.5:4b")

    assert result["readiness_status"] == readiness.MODEL_UNAVAILABLE_STATUS
    assert result["passed_count"] == result["check_count"]


def test_ollama_llm_readiness_available_passes(monkeypatch):
    monkeypatch.setattr(readiness, "check_ollama_availability", lambda **kwargs: _availability("available"))
    monkeypatch.setattr(readiness, "run_ollama_llm_experiment", lambda **kwargs: _experiment("no_records_available"))
    monkeypatch.setattr(
        readiness,
        "run_qwen_ollama_smoke",
        lambda **kwargs: {"created_temp_store": True, "smoke_status": "smoke_completed", "experiment": _experiment("completed")},
    )

    result = readiness.run_ollama_llm_readiness_gate(model="qwen3.5:4b")

    assert result["readiness_status"] == readiness.READY_STATUS
    assert result["passed_count"] == result["check_count"]


def test_ollama_llm_readiness_report_renders_status(monkeypatch):
    monkeypatch.setattr(readiness, "check_ollama_availability", lambda **kwargs: _availability("ollama_unavailable"))
    monkeypatch.setattr(readiness, "run_ollama_llm_experiment", lambda **kwargs: _experiment("no_records_available"))
    monkeypatch.setattr(
        readiness,
        "run_qwen_ollama_smoke",
        lambda **kwargs: {"created_temp_store": True, "smoke_status": "ollama_unavailable", "experiment": _experiment("ollama_unavailable")},
    )

    report = readiness.render_ollama_llm_readiness_report(readiness.run_ollama_llm_readiness_gate(model="qwen3.5:4b"))

    assert "Ollama LLM Readiness" in report
    assert readiness.OLLAMA_UNAVAILABLE_STATUS in report


def test_ollama_llm_readiness_cli_exits_cleanly():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.ollama_llm_readiness",
            "--model",
            "qwen3.5:4b",
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Ollama LLM Readiness" in completed.stdout
