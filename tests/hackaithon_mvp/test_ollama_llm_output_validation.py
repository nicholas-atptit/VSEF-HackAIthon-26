from src.hackaithon_mvp.llm_storage_contract import CLAIM_BOUNDARY, CREATED_AT
from src.hackaithon_mvp.local_evidence_store import write_llm_readable_records
from src.hackaithon_mvp.ollama_llm_experiment import (
    classify_llm_output_safety,
    run_ollama_llm_experiment,
    validate_llm_answer_safety,
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


def test_llm_answer_safety_allows_boundary_statements():
    safe_action_output = "No " + "/".join(("buy", "sell", "hold")) + " output is produced."
    safe_guidance = "It does not constitute market guidance."
    allowed_answers = (
        "This is not a trading signal.",
        "The system does not produce trading labels.",
        "This is diagnostic-only and human review is required.",
        safe_action_output,
        "This should not be treated as financial advice.",
        safe_guidance,
        "This is research-only and not a production system.",
        "There is no live trading.",
    )

    for answer in allowed_answers:
        result = validate_llm_answer_safety(answer)
        assert result["is_allowed"] is True, answer
        assert result["safety_classification"] == "allowed"
        assert result["blocked_terms"] == ()


def test_llm_answer_safety_blocks_action_and_overclaim_wording():
    blocked_answers = (
        "BUY VCB now.",
        "SELL this stock.",
        "HOLD the position.",
        "You should buy this ticker.",
        "This is a live trading signal.",
        "The system guarantees profit.",
        "The model achieved production trading performance.",
        "Use this price target for the ticker.",
        "You should enter a trade.",
    )

    for answer in blocked_answers:
        result = validate_llm_answer_safety(answer)
        assert result["is_allowed"] is False, answer
        assert result["blocked_terms"]
        assert result["safety_classification"].startswith("blocked_")


def test_llm_answer_safety_reports_allowed_boundary_terms():
    result = classify_llm_output_safety("This is not a trading signal. Human review is required.")

    assert result["is_allowed"] is True
    assert "not a trading signal" in result["allowed_boundary_terms"]
    assert "human review required" in result["allowed_boundary_terms"]


def test_safe_boundary_model_answer_is_not_overwritten(tmp_path, monkeypatch):
    write_llm_readable_records(records=(_record(),), store_root=str(tmp_path))

    def fake_call(**kwargs):
        return {
            "call_status": "completed",
            "model": kwargs["model"],
            "llm_called": True,
            "answer": "This is not a trading signal. Human review is required. Source: source-1.",
            "errors": [],
            "message": "completed",
            "model_response_debug": {"answer_length": 76},
        }

    monkeypatch.setattr("src.hackaithon_mvp.ollama_llm_experiment.call_ollama_chat", fake_call)

    result = run_ollama_llm_experiment(
        store_root=str(tmp_path),
        query="explain why this is not a trading signal",
        model="qwen3.5:4b",
    )

    assert result["experiment_status"] == "completed"
    assert result["abstained"] is False
    assert "not a trading signal" in result["answer"]
    assert result["answer_safety"]["is_allowed"] is True


def test_unsafe_model_answer_is_blocked(tmp_path, monkeypatch):
    write_llm_readable_records(records=(_record(),), store_root=str(tmp_path))

    def fake_call(**kwargs):
        action_word = "".join(("b", "uy"))
        return {
            "call_status": "completed",
            "model": kwargs["model"],
            "llm_called": True,
            "answer": f"You should {action_word} this ticker. Source: source-1.",
            "errors": [],
            "message": "completed",
            "model_response_debug": {"answer_length": 44},
        }

    monkeypatch.setattr("src.hackaithon_mvp.ollama_llm_experiment.call_ollama_chat", fake_call)

    result = run_ollama_llm_experiment(
        store_root=str(tmp_path),
        query="diagnostic boundary",
        model="qwen3.5:4b",
    )

    assert result["experiment_status"] == "blocked_by_output_validation"
    assert result["abstained"] is True
    assert result["answer_safety"]["is_allowed"] is False
    assert result["answer_safety"]["safety_classification"] == "blocked_action_label"
