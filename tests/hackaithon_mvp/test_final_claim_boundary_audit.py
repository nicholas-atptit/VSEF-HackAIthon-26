import subprocess
import sys

from src.hackaithon_mvp.final_claim_boundary_audit import (
    render_final_claim_boundary_report,
    run_final_claim_boundary_audit,
)


def _safe_readme() -> str:
    return """
# HackAIthon MVP

research-only diagnostic-only baseline ml-only human-review required
no data gateway no live data no provider api calls no model training no model inference no benchmark rerun
no action-oriented output no production readiness claim no profitability guarantee
python -m src.hackaithon_mvp.end_to_end_demo
python -m pytest tests/hackaithon_mvp -q --basetemp .pytest-tmp
999 passed

77,850 is a generated diagnostic engine-spec universe.
The latest sweep has low evidence coverage and needs more dependency outputs.
Offline Gateway v0 is local-file only.
Optional local Ollama evidence explanation is read-only.
The tuning readiness control plane does not update models.
Generated artifacts remain untracked.
Human review remains required.
"""


def test_final_claim_boundary_audit_passes_safe_readme(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(_safe_readme(), encoding="utf-8")

    result = run_final_claim_boundary_audit(readme_path=str(path))

    assert result["audit_status"] == "ready_for_public_demo_claim_review"
    assert result["is_safe"] is True
    assert result["errors"] == []


def test_final_claim_boundary_audit_blocks_forbidden_public_claims(tmp_path):
    path = tmp_path / "README.md"
    action_word = "".join(("b", "uy"))
    path.write_text(_safe_readme() + f"\nThis is a {action_word} instruction.\n", encoding="utf-8")

    result = run_final_claim_boundary_audit(readme_path=str(path))

    assert result["audit_status"] == "claim_boundary_attention_required"
    assert result["is_safe"] is False
    assert result["errors"]


def test_final_claim_boundary_report_renders_status(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(_safe_readme(), encoding="utf-8")
    report = render_final_claim_boundary_report(run_final_claim_boundary_audit(readme_path=str(path)))

    assert "Final Claim Boundary Audit" in report
    assert "Audit status: ready_for_public_demo_claim_review" in report


def test_final_claim_boundary_audit_current_readme_runs():
    result = run_final_claim_boundary_audit()

    assert result["audit_status"] in {
        "ready_for_public_demo_claim_review",
        "claim_boundary_attention_required",
    }


def test_final_claim_boundary_audit_cli_report_exits_for_safe_readme(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(_safe_readme(), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.hackaithon_mvp.final_claim_boundary_audit",
            "--readme",
            str(path),
            "--format",
            "report",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Audit status: ready_for_public_demo_claim_review" in completed.stdout
