from src.hackaithon_mvp.diagnostic_engine import (
    render_diagnostic_engine_report,
    run_diagnostic_engine_from_payload,
)
from src.hackaithon_mvp.engine_input_contract import build_minimal_engine_input_fixture


def test_diagnostic_engine_payload_orchestration_includes_v2_sections():
    result = run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture())

    assert result["engine_status"] == "completed_gateway_ready_local_engine_core"
    assert result["input_validation"]["is_valid"] is True
    assert result["dag_output"]["execution_status"].startswith("completed")
    assert result["ml_engine"]["ml_engine_status"] == "completed"
    assert result["scenario_engine_v2"]["scenario_engine_status"] == "completed"
    assert result["risk_engine_v2"]["risk_engine_status"] == "completed"
    assert result["decision_lane_v2"]["human_review_required"] is True
    assert result["decision_lane_v2"]["auto_execution_allowed"] is False
    assert result["engine_completeness"]["completeness_status"] == "complete"


def test_diagnostic_engine_invalid_payload_returns_safe_failure():
    payload = build_minimal_engine_input_fixture()
    payload["request"]["ticker"] = ""

    result = run_diagnostic_engine_from_payload(payload)

    assert result["engine_status"] == "safe_failure_invalid_input"
    assert result["decision_lane_v2"]["lane"] == "blocked_pending_risk_review"
    assert result["risk_engine_v2"]["risk_level"] == "critical"


def test_diagnostic_engine_report_mentions_v2_layers():
    report = render_diagnostic_engine_report(run_diagnostic_engine_from_payload(build_minimal_engine_input_fixture()))

    assert "ML engine:" in report
    assert "Scenario Engine V2:" in report
    assert "Risk Engine V2:" in report
    assert "Decision Lane V2:" in report
    assert "Auto execution allowed: False" in report
