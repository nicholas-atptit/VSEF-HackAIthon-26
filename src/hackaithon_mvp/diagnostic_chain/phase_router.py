"""Layer 8: diagnostic phase router."""

from __future__ import annotations

from .chain_schema import (
    ALLOWED_ROUTES,
    NON_CLAIM_TEXT,
    PhaseRouterOutput,
    assert_allowed,
    assert_no_forbidden_public_terms,
)


def run_phase_router(decision_output: dict, risk_output: dict, allocator_output: dict) -> PhaseRouterOutput:
    lane = str(decision_output.get("decision_lane", "evidence_insufficient"))
    risk_level = str(risk_output.get("risk_level", "high"))
    allocation_view = str(allocator_output.get("allocation_view", "insufficient_evidence"))

    if lane == "evidence_insufficient" or allocation_view == "insufficient_evidence":
        route = "evidence_insufficient"
        explanation = "Static evidence is insufficient for candidate routing."
    elif lane == "exploratory_only":
        route = "exploratory_only"
        explanation = "The chain remains exploratory under reviewer control."
    elif risk_level in {"high", "critical"}:
        route = "escalate"
        explanation = "Risk level requires human escalation."
    elif allocation_view == "no_allocation" and lane == "reject_as_weak_evidence":
        route = "reject"
        explanation = "Evidence is weak and the research sizing view is closed."
    elif allocation_view == "no_allocation":
        route = "maintain_watchlist_review"
        explanation = "Keep the item in watchlist review without candidate routing."
    else:
        route = "route_candidate"
        explanation = "Route the diagnostic candidate for human review."

    assert_allowed(route, ALLOWED_ROUTES, "route")
    output: PhaseRouterOutput = {
        "route": route,
        "dashboard_status": "not_enabled_for_this_slice",
        "human_review_required": True,
        "explanation": explanation,
        "non_claim": NON_CLAIM_TEXT,
    }
    assert_no_forbidden_public_terms(output)
    return output
