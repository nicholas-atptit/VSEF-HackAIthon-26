import json
import subprocess
import sys

from src.hackaithon_mvp import ollama_local_client as client


def test_ollama_client_config_defaults_to_local_host_only(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    config = client.build_ollama_client_config()

    assert config["config_status"] == "ready"
    assert config["base_url"] == "http://127.0.0.1:11434"
    assert config["model"] == "qwen3.5:4b"
    assert config["localhost_only"] is True
    assert config["auto_pull_enabled"] is False


def test_ollama_client_model_precedence(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "local-env-model")

    env_config = client.build_ollama_client_config()
    arg_config = client.build_ollama_client_config(model="local-arg-model")

    assert env_config["model"] == "local-env-model"
    assert arg_config["model"] == "local-arg-model"


def test_ollama_client_rejects_non_loopback_url():
    config = client.build_ollama_client_config(base_url="http://example.com:11434")
    availability = client.check_ollama_availability(base_url="http://example.com:11434")

    assert config["config_status"] == "invalid_base_url"
    assert availability["availability_status"] == "invalid_base_url"


def test_check_ollama_availability_missing_returns_clean_status(monkeypatch):
    def fake_request_json(**kwargs):
        return None, "URLError"

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    result = client.check_ollama_availability(model="qwen3.5:4b")

    assert result["availability_status"] == "ollama_unavailable"
    assert "ollama list" in result["message"]
    assert result["errors"] == ["URLError"]


def test_check_ollama_availability_missing_model_returns_clean_status(monkeypatch):
    def fake_request_json(**kwargs):
        return {"models": [{"name": "installed:tag"}]}, None

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    result = client.check_ollama_availability(model="qwen3.5:4b")

    assert result["availability_status"] == "model_unavailable"
    assert result["available_models"] == ["installed:tag"]


def test_build_ollama_chat_payload_is_bounded():
    payload = client.build_ollama_chat_payload(
        model="qwen3.5:4b",
        system_prompt="s" * 9000,
        user_prompt="u" * 17000,
        temperature=5.0,
    )

    assert payload["model"] == "qwen3.5:4b"
    assert payload["stream"] is False
    assert len(payload["messages"][0]["content"]) == 8000
    assert len(payload["messages"][1]["content"]) == 16000
    assert payload["options"]["temperature"] == 1.0
    assert payload["options"]["num_predict"] == 512


def test_call_ollama_chat_fake_available_model_returns_answer(monkeypatch):
    def fake_availability(**kwargs):
        return {
            "availability_status": "available",
            "model": kwargs["model"],
            "base_url": "http://127.0.0.1:11434",
            "errors": [],
        }

    def fake_request_json(**kwargs):
        return {"message": {"content": "Answer from local retrieved evidence."}, "done": True}, None

    monkeypatch.setattr(client, "check_ollama_availability", fake_availability)
    monkeypatch.setattr(client, "_request_json", fake_request_json)

    result = client.call_ollama_chat(
        model="qwen3.5:4b",
        system_prompt="system",
        user_prompt="user",
    )

    assert result["call_status"] == "completed"
    assert result["llm_called"] is True
    assert result["answer"] == "Answer from local retrieved evidence."


def test_ollama_local_client_cli_check_exits_cleanly(monkeypatch):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.ollama_local_client",
            "--check",
            "--model",
            "qwen3.5:4b",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["availability_status"] in {"available", "ollama_unavailable", "model_unavailable"}
