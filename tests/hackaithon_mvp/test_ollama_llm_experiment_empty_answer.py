from src.hackaithon_mvp.llm_storage_contract import CLAIM_BOUNDARY, CREATED_AT
from src.hackaithon_mvp.local_evidence_store import write_llm_readable_records
from src.hackaithon_mvp.ollama_llm_experiment import (
    EMPTY_MODEL_ANSWER,
    INSUFFICIENT_EVIDENCE_ANSWER,
    run_ollama_llm_experiment,
)


def _record(record_id: str = "source-1") -> dict:
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


def test_empty_model_answer_is_not_reported_as_missing_evidence(tmp_path, monkeypatch):
    write_llm_readable_records(records=(_record(),), store_root=str(tmp_path))

    def fake_call(**kwargs):
        return {
            "call_status": "completed",
            "model": kwargs["model"],
            "llm_called": True,
            "answer": "",
            "errors": [],
            "message": "completed",
            "model_response_debug": {
                "raw_response_keys": ["message"],
                "content_extraction_path": "empty",
                "thinking_present": True,
                "answer_length": 0,
            },
        }

    monkeypatch.setattr("src.hackaithon_mvp.ollama_llm_experiment.call_ollama_chat", fake_call)

    result = run_ollama_llm_experiment(
        store_root=str(tmp_path),
        query="diagnostic boundary",
        model="qwen3.5:4b",
    )

    assert result["experiment_status"] == "completed_empty_model_answer"
    assert result["llm_called"] is True
    assert result["abstained"] is True
    assert result["answer"] == EMPTY_MODEL_ANSWER
    assert result["answer"] != INSUFFICIENT_EVIDENCE_ANSWER
    assert result["model_response_debug"]["thinking_present"] is True
    assert result["source_ids"] == ["source-1"]


def test_non_empty_model_answer_is_not_overwritten(tmp_path, monkeypatch):
    write_llm_readable_records(records=(_record(),), store_root=str(tmp_path))

    def fake_call(**kwargs):
        return {
            "call_status": "completed",
            "model": kwargs["model"],
            "llm_called": True,
            "answer": "The retrieved source says this is read-only diagnostic context. Source: source-1.",
            "errors": [],
            "message": "completed",
            "model_response_debug": {
                "raw_response_keys": ["message"],
                "content_extraction_path": "message.content",
                "thinking_present": False,
                "answer_length": 78,
            },
        }

    monkeypatch.setattr("src.hackaithon_mvp.ollama_llm_experiment.call_ollama_chat", fake_call)

    result = run_ollama_llm_experiment(
        store_root=str(tmp_path),
        query="diagnostic boundary",
        model="qwen3.5:4b",
    )

    assert result["experiment_status"] == "completed"
    assert result["llm_called"] is True
    assert result["abstained"] is False
    assert "read-only diagnostic context" in result["answer"]
    assert result["model_response_debug"]["content_extraction_path"] == "message.content"
