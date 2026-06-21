from src.hackaithon_mvp.llm_storage_contract import CLAIM_BOUNDARY, CREATED_AT
from src.hackaithon_mvp.local_evidence_store import write_llm_readable_records
from src.hackaithon_mvp.ollama_llm_experiment import (
    build_evidence_grounded_user_prompt,
    build_llm_system_prompt,
    run_ollama_llm_experiment,
    validate_llm_experiment_result,
)


def _record(record_id: str = "record-a") -> dict:
    return {
        "record_id": record_id,
        "record_type": "engine_run_summary",
        "title": "Diagnostic engine boundary",
        "summary": "Read-only diagnostic context.",
        "content": {"topic": "diagnostic engine boundary", "human_review_required": True},
        "source_module": "test",
        "created_at": CREATED_AT,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": "Local evidence context for research diagnostics; read-only retrieval only.",
        "human_review_required": True,
        "read_only": True,
    }


def test_llm_prompts_require_context_only_and_source_ids():
    system_prompt = build_llm_system_prompt()
    user_prompt = build_evidence_grounded_user_prompt(
        query="diagnostic boundary",
        retrieved_context={
            "retrieval_status": "records_available",
            "records": [_record("source-1")],
        },
    )

    assert "answer only from" in system_prompt
    assert "source IDs" in system_prompt
    assert "source-1" in user_prompt
    assert "diagnostic boundary" in user_prompt


def test_llm_experiment_abstains_if_no_records(tmp_path):
    result = run_ollama_llm_experiment(
        store_root=str(tmp_path / "missing"),
        query="diagnostic boundary",
        model="qwen3.5:4b",
    )

    assert result["experiment_status"] == "no_records_available"
    assert result["llm_called"] is False
    assert result["abstained"] is True
    assert result["read_only"] is True


def test_llm_experiment_handles_unavailable_ollama_cleanly(tmp_path, monkeypatch):
    write_llm_readable_records(records=(_record("source-1"),), store_root=str(tmp_path))

    def fake_call(**kwargs):
        return {
            "call_status": "ollama_unavailable",
            "model": kwargs["model"],
            "llm_called": False,
            "answer": "",
            "errors": ["URLError"],
            "message": "unavailable",
        }

    monkeypatch.setattr("src.hackaithon_mvp.ollama_llm_experiment.call_ollama_chat", fake_call)

    result = run_ollama_llm_experiment(
        store_root=str(tmp_path),
        query="diagnostic boundary",
        model="qwen3.5:4b",
    )

    assert result["experiment_status"] == "ollama_unavailable"
    assert result["llm_called"] is False
    assert result["source_ids"] == ["source-1"]
    assert result["abstained"] is True


def test_llm_experiment_fake_model_returns_answer_with_sources(tmp_path, monkeypatch):
    write_llm_readable_records(records=(_record("source-1"),), store_root=str(tmp_path))

    def fake_call(**kwargs):
        return {
            "call_status": "completed",
            "model": kwargs["model"],
            "llm_called": True,
            "answer": "The retrieved context says the run is read-only and human-reviewed. Source: source-1.",
            "errors": [],
            "message": "completed",
        }

    monkeypatch.setattr("src.hackaithon_mvp.ollama_llm_experiment.call_ollama_chat", fake_call)

    result = run_ollama_llm_experiment(
        store_root=str(tmp_path),
        query="diagnostic boundary",
        model="qwen3.5:4b",
    )

    assert result["experiment_status"] == "completed"
    assert result["llm_called"] is True
    assert result["source_ids"] == ["source-1"]
    assert validate_llm_experiment_result(result)["is_valid"] is True


def test_llm_experiment_validation_catches_action_labels():
    action_word = "".join(("b", "uy"))
    result = {
        "experiment_status": "completed",
        "answer": f"This says {action_word}.",
        "source_ids": ["source-1"],
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
    }

    validation = validate_llm_experiment_result(result)

    assert validation["is_valid"] is False
    assert any("action labels" in error for error in validation["errors"])


def test_llm_experiment_validation_catches_restricted_public_wording():
    restricted_word = "".join(("deploy", "ment"))
    result = {
        "experiment_status": "completed",
        "answer": f"This answer includes {restricted_word} wording.",
        "source_ids": ["source-1"],
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
    }

    validation = validate_llm_experiment_result(result)

    assert validation["is_valid"] is False
    assert any("restricted public wording" in error for error in validation["errors"])


def test_llm_experiment_validation_catches_restricted_market_phrase():
    restricted_phrase = " ".join(("trading", "signals"))
    result = {
        "experiment_status": "completed",
        "answer": f"This answer repeats {restricted_phrase}.",
        "source_ids": ["source-1"],
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
    }

    validation = validate_llm_experiment_result(result)

    assert validation["is_valid"] is False
    assert any("restricted market-action wording" in error for error in validation["errors"])
