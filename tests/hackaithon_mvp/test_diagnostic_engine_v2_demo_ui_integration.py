import subprocess
import sys

from src.hackaithon_mvp.demo_ui import build_demo_ui_summary, render_demo_ui_text
from src.hackaithon_mvp.diagram_demo_readiness import build_diagram_demo_readiness_summary


def test_demo_ui_includes_all_v2_engine_sections():
    summary = build_demo_ui_summary()
    text = render_demo_ui_text(summary)

    assert "Gateway-ready input contract" in text
    assert "ML Diagnostic Engine" in text
    assert "Risk Engine V2" in text
    assert "Scenario Engine V2" in text
    assert "Decision Lane V2" in text
    assert "Hardening gate status" in text
    assert summary["decision_lane_v2"]["auto_execution_allowed"] is False


def test_diagram_readiness_includes_v2_fields():
    summary = build_diagram_demo_readiness_summary()

    assert summary["gateway_input_contract_ready"] is True
    assert summary["ml_diagnostic_engine_ready"] is True
    assert summary["risk_engine_v2_ready"] is True
    assert summary["scenario_engine_v2_ready"] is True
    assert summary["decision_lane_v2_ready"] is True
    assert summary["hardening_gate_status"] == "accepted_for_gateway_ready_local_engine_core"


def test_demo_ui_cli_text_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.demo_ui", "--format", "text"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Diagnostic Engine Demo" in completed.stdout
    assert "Decision Lane V2" in completed.stdout
