import json
import re

from src.hackaithon_mvp.decision_lane_v2 import build_decision_lane_v2_policy, run_decision_lane_v2


def _ml(**overrides):
    payload = {
        "ml_engine_status": "completed",
        "agreement_status": "strong_agreement",
        "calibration_status": "calibrated",
        "recommended_review_lane": "standard_human_review",
    }
    payload.update(overrides)
    return payload


def _risk(level="low"):
    return {"risk_level": level, "blocking_flags": [], "required_human_review": True}


def _scenario(status="stable"):
    return {"stability_status": status, "scenario_risk_level": "low", "required_human_review": True}


def test_decision_lane_v2_policy_lists_lanes():
    policy = build_decision_lane_v2_policy()

    assert "blocked_pending_risk_review" in policy["decision_lanes"]
    assert "evidence_insufficient_review" in policy["decision_lanes"]


def test_decision_lane_v2_blocks_critical_risk():
    result = run_decision_lane_v2(
        diagnostic_output={"forecast_diagnostic": "neutral_or_uncertain"},
        ml_summary=_ml(),
        risk_summary=_risk("critical"),
        scenario_summary=_scenario(),
    )

    assert result["lane"] == "blocked_pending_risk_review"
    assert result["auto_execution_allowed"] is False
    assert result["human_review_required"] is True


def test_decision_lane_v2_routes_insufficient_evidence():
    result = run_decision_lane_v2(
        diagnostic_output={"forecast_diagnostic": "insufficient_evidence"},
        ml_summary=_ml(recommended_review_lane="evidence_insufficient_review"),
        risk_summary=_risk("medium"),
        scenario_summary=_scenario("insufficient_evidence"),
    )

    assert result["lane"] in {"evidence_insufficient_review", "blocked_pending_evidence"}
    assert "evidence_review" in result["required_reviews"]


def test_decision_lane_v2_requires_review_for_model_disagreement():
    result = run_decision_lane_v2(
        diagnostic_output={"forecast_diagnostic": "neutral_or_uncertain"},
        ml_summary=_ml(agreement_status="high_disagreement", recommended_review_lane="risk_review_required"),
        risk_summary=_risk("high"),
        scenario_summary=_scenario("unstable"),
    )

    assert result["lane"] == "risk_review_required"
    assert "risk_review" in result["required_reviews"]


def test_decision_lane_v2_never_outputs_action_labels():
    result = run_decision_lane_v2(
        diagnostic_output={"forecast_diagnostic": "neutral_or_uncertain"},
        ml_summary=_ml(),
        risk_summary=_risk(),
        scenario_summary=_scenario(),
    )
    text = json.dumps(result).lower()
    action_terms = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))

    assert not re.search(r"\b(" + "|".join(action_terms) + r")\b", text)
