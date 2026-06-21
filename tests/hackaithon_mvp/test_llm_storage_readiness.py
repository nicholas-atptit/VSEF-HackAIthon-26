import subprocess
import sys

from src.hackaithon_mvp.llm_storage_readiness import (
    render_llm_storage_readiness_report,
    run_llm_storage_readiness_gate,
)


def test_llm_storage_readiness_gate_passes():
    result = run_llm_storage_readiness_gate()

    assert result["readiness_status"] == "ready_for_local_llm_readable_evidence_store"
    assert result["passed_count"] == result["check_count"]
    assert result["read_only"] is True
    assert result["human_review_required"] is True


def test_llm_storage_readiness_report_renders_status():
    report = render_llm_storage_readiness_report(run_llm_storage_readiness_gate())

    assert "# LLM Storage Readiness" in report
    assert "ready_for_local_llm_readable_evidence_store" in report
    assert "Read-only: True" in report


def test_llm_storage_readiness_cli_report_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.llm_storage_readiness", "--format", "report"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "ready_for_local_llm_readable_evidence_store" in completed.stdout
