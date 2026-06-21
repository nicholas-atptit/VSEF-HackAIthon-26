from pathlib import Path

from src.hackaithon_mvp import qwen_ollama_smoke as smoke


def test_qwen_ollama_smoke_removes_internal_temp_store(monkeypatch):
    temp_paths: list[str] = []

    def fake_mkdtemp(prefix):
        path = Path.cwd() / ".pytest-tmp" / "internal-ollama-smoke"
        path.mkdir(parents=True, exist_ok=True)
        temp_paths.append(str(path))
        return str(path)

    def fake_experiment(**kwargs):
        assert kwargs["store_root"] == temp_paths[0]
        return {
            "experiment_status": "ollama_unavailable",
            "llm_called": False,
            "retrieved_record_count": 1,
            "source_ids": ["source-1"],
            "answer": "Insufficient retrieved evidence to answer from the local context.",
            "abstained": True,
        }

    monkeypatch.setattr(smoke.tempfile, "mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(smoke, "run_ollama_llm_experiment", fake_experiment)

    result = smoke.run_qwen_ollama_smoke(model="qwen3.5:4b")

    assert result["created_temp_store"] is True
    assert result["smoke_status"] == "ollama_unavailable"
    assert not Path(temp_paths[0]).exists()


def test_qwen_ollama_smoke_uses_supplied_store_without_writing(monkeypatch, tmp_path):
    called = {"write": False}

    def fake_write(**kwargs):
        called["write"] = True
        return {"write_status": "written_local_jsonl"}

    def fake_experiment(**kwargs):
        assert kwargs["store_root"] == str(tmp_path)
        return {
            "experiment_status": "no_records_available",
            "llm_called": False,
            "retrieved_record_count": 0,
            "source_ids": [],
            "answer": "Insufficient retrieved evidence to answer from the local context.",
            "abstained": True,
        }

    monkeypatch.setattr(smoke, "write_llm_readable_records", fake_write)
    monkeypatch.setattr(smoke, "run_ollama_llm_experiment", fake_experiment)

    result = smoke.run_qwen_ollama_smoke(model="qwen3.5:4b", store_root=str(tmp_path))

    assert result["created_temp_store"] is False
    assert result["write_status"] == "not_written"
    assert called["write"] is False


def test_qwen_ollama_smoke_report_renders_clean_status():
    report = smoke.render_qwen_ollama_smoke_report(
        {
            "smoke_status": "ollama_unavailable",
            "model": "qwen3.5:4b",
            "created_temp_store": True,
            "temp_store_removed": False,
            "write_status": "written_local_jsonl",
            "experiment": {"experiment_status": "ollama_unavailable", "llm_called": False, "retrieved_record_count": 1},
            "non_claim": "Local evidence context for research diagnostics; read-only retrieval only.",
        }
    )

    assert "Qwen Ollama Smoke" in report
    assert "Temp store removed: True" in report
    assert "ollama_unavailable" in report
