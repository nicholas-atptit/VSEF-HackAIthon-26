import json

from src.hackaithon_mvp import ollama_local_client as client


def test_decode_ollama_response_body_handles_streamed_ndjson():
    body = b'{"message":{"content":"Hel"}}\n{"message":{"content":"lo"},"done":true}\n'

    payload, error = client._decode_ollama_response_body(body)
    answer, debug = client._extract_ollama_answer(payload)

    assert error is None
    assert answer == "Hello"
    assert debug["content_extraction_path"] == "stream.message.content"
    assert debug["answer_length"] == 5


def test_extract_ollama_answer_prefers_chat_message_content():
    answer, debug = client._extract_ollama_answer({"message": {"content": "PONG"}, "done": True})

    assert answer == "PONG"
    assert debug["content_extraction_path"] == "message.content"
    assert debug["thinking_present"] is False
    assert debug["answer_length"] == 4


def test_extract_ollama_answer_uses_generate_response():
    answer, debug = client._extract_ollama_answer({"response": "PONG", "done": True})

    assert answer == "PONG"
    assert debug["content_extraction_path"] == "response"
    assert debug["answer_length"] == 4


def test_extract_ollama_answer_keeps_thinking_out_of_answer():
    answer, debug = client._extract_ollama_answer(
        {"message": {"content": "", "thinking": "internal reasoning"}, "done": True}
    )

    assert answer == ""
    assert debug["thinking_present"] is True
    assert debug["content_extraction_path"] == "empty"
    assert debug["answer_length"] == 0


def test_call_ollama_chat_falls_back_to_generate_response(monkeypatch):
    requests = []

    def fake_availability(**kwargs):
        return {
            "availability_status": "available",
            "model": kwargs["model"],
            "base_url": "http://127.0.0.1:11434",
            "errors": [],
        }

    def fake_request_json(**kwargs):
        requests.append(kwargs)
        if kwargs["url"].endswith("/api/chat"):
            return {"message": {"content": "", "thinking": "thinking only"}, "done": True}, None
        return {"response": "Answer from generated final content.", "done": True}, None

    monkeypatch.setattr(client, "check_ollama_availability", fake_availability)
    monkeypatch.setattr(client, "_request_json", fake_request_json)

    result = client.call_ollama_chat(
        model="qwen3.5:4b",
        system_prompt="system",
        user_prompt="user",
    )

    assert result["call_status"] == "completed"
    assert result["answer"] == "Answer from generated final content."
    assert result["content_extraction_path"] == "response"
    assert result["model_response_debug"]["fallback_used"] == "api_generate"
    chat_payload = requests[0]["payload"]
    assert chat_payload["stream"] is False
    assert chat_payload["think"] is False


def test_decode_ollama_response_body_rejects_non_object_json():
    payload, error = client._decode_ollama_response_body(json.dumps(["not", "object"]).encode("utf-8"))

    assert payload is None
    assert error == "invalid_json:payload_not_object"
