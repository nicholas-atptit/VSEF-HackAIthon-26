import subprocess
import sys

from src.hackaithon_mvp.diagram_demo_readiness import (
    build_diagram_demo_readiness_summary,
    render_diagram_demo_readiness_report,
)


def test_diagram_demo_readiness_aggregates_all_modules():
    summary = build_diagram_demo_readiness_summary()

    assert summary["readiness_status"] == "ready_for_local_diagram_demo_after_human_review"
    assert summary["checks"]["dag_forecast_verification"] is True
    assert summary["checks"]["diagram_coverage_matrix"] is True
    assert summary["checks"]["architecture_alignment"] is True
    assert summary["checks"]["periodic_runner_contract"] is True
    assert summary["checks"]["dashboard_artifact_export"] is True
    assert summary["checks"]["social_listening_contract"] is True
    assert summary["checks"]["feedback_loop_contract"] is True


def test_diagram_demo_readiness_report_renders_summary():
    report = render_diagram_demo_readiness_report(build_diagram_demo_readiness_summary())

    assert "# Diagram Demo Readiness" in report
    assert "DAG Forecast Verification" in report
    assert "Diagram Coverage" in report
    assert "Local Contracts" in report
    assert "Human review remains required." in report


def test_diagram_demo_readiness_cli_report_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.diagram_demo_readiness", "--format", "report"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "ready_for_local_diagram_demo_after_human_review" in completed.stdout
