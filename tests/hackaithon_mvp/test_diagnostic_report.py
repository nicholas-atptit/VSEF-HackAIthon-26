from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain
from src.hackaithon_mvp.diagnostic_report import REPORT_TITLE, render_diagnostic_report
from src.hackaithon_mvp.evidence_packet import build_evidence_packet


REQUIRED_SECTIONS = (
    "# HackAIthon MVP Diagnostic Routing Report",
    "## Scope",
    "## Timeframe",
    "## Diagnostic Summary",
    "## Forecast Diagnostic",
    "## Scenario and Risk",
    "## Routing",
    "## Evidence Boundary",
    "## Human Review Requirement",
)


def test_diagnostic_report_renders_required_sections():
    chain_output = run_diagnostic_chain("VCB", sample_size=20, timeframe="1 ngày")
    packet = build_evidence_packet(chain_output, run_metadata={"run_id": "unit-run"})
    report = render_diagnostic_report(packet)

    assert REPORT_TITLE in report
    for section in REQUIRED_SECTIONS:
        assert section in report


def test_diagnostic_report_includes_timeframe_and_key_summaries():
    chain_output = run_diagnostic_chain("VCB", sample_size=20, timeframe="1 ngày")
    packet = build_evidence_packet(chain_output, run_metadata={"run_id": "unit-run"})
    report = render_diagnostic_report(packet)

    assert "Timeframe: 1d (day)" in report
    assert "Quant signal:" in report
    assert "Route:" in report
    assert "Human review required: True" in report
