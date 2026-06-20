from src.hackaithon_mvp.public_demo_readiness import (
    build_public_demo_readiness_summary,
    render_public_demo_readiness_report,
)


def test_report_is_neutral_and_bounded():
    report = render_public_demo_readiness_report(build_public_demo_readiness_summary())

    assert "Public Demo Readiness" in report
    assert "Local-only readiness check. No file writes are performed." in report
    assert "Human review remains required." in report
    assert "Readiness status: ready_with_manual_review" in report


def test_report_summarizes_command_and_audit_status():
    report = render_public_demo_readiness_report(build_public_demo_readiness_summary())

    assert "Demo command count: 6" in report
    assert "Default commands write files: False" in report
    assert "Requires live data: False" in report
    assert "Runs training: False" in report
    assert "README safe: True" in report
    assert "Claim boundary safe: True" in report
