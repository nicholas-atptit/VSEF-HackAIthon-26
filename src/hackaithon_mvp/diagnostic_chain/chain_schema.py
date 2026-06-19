"""Shared schema and validation for the diagnostic decision chain."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Literal, TypedDict


QuantSignal = Literal[
    "positive_bias",
    "negative_bias",
    "neutral_or_uncertain",
    "insufficient_evidence",
    "exploratory_only",
]
ScenarioLabel = Literal["growth", "neutral", "correction", "uncertain"]
RiskLevel = Literal["low", "medium", "high", "critical"]
DecisionLane = Literal[
    "research_candidate",
    "watchlist_review",
    "reject_as_weak_evidence",
    "escalate_for_review",
    "evidence_insufficient",
    "exploratory_only",
]
AllocationView = Literal[
    "no_allocation",
    "research_weight_candidate",
    "risk_capped_candidate",
    "insufficient_evidence",
]
RouteLabel = Literal[
    "route_candidate",
    "maintain_watchlist_review",
    "reject",
    "escalate",
    "evidence_insufficient",
    "exploratory_only",
]

ALLOWED_QUANT_SIGNALS = frozenset(
    {
        "positive_bias",
        "negative_bias",
        "neutral_or_uncertain",
        "insufficient_evidence",
        "exploratory_only",
    }
)
ALLOWED_SCENARIOS = frozenset({"growth", "neutral", "correction", "uncertain"})
ALLOWED_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})
ALLOWED_DECISION_LANES = frozenset(
    {
        "research_candidate",
        "watchlist_review",
        "reject_as_weak_evidence",
        "escalate_for_review",
        "evidence_insufficient",
        "exploratory_only",
    }
)
ALLOWED_ALLOCATION_VIEWS = frozenset(
    {
        "no_allocation",
        "research_weight_candidate",
        "risk_capped_candidate",
        "insufficient_evidence",
    }
)
ALLOWED_ROUTES = frozenset(
    {
        "route_candidate",
        "maintain_watchlist_review",
        "reject",
        "escalate",
        "evidence_insufficient",
        "exploratory_only",
    }
)

FORBIDDEN_PUBLIC_TERMS = (
    "BUY",
    "SELL",
    "HOLD",
    "strong buy",
    "strong sell",
    "recommendation",
    "trade",
    "trading signal",
    "investment advice",
    "guaranteed profit",
    "portfolio allocation advice",
)

NON_CLAIM_TEXT = "Research diagnostic only; static local evidence boundary applies."


class QuantCoreOutput(TypedDict):
    ticker: str
    quant_signal: str
    consensus_strength: float
    engine_count_checked: int
    completed_count: int
    skipped_missing_evidence_count: int
    forecast_diagnostic_engine_enabled: bool
    forecast_diagnostic_counts: dict[str, int]
    forecast_diagnostic_sample: list[dict[str, Any]]
    warnings: list[str]
    non_claim: str


class ScenarioOutput(TypedDict):
    scenario: str
    scenario_probabilities: dict[str, float]
    scenario_confidence: float
    explanation: str


class RiskGovernanceOutput(TypedDict):
    risk_level: str
    risk_flags: list[str]
    risk_action: str
    explanation: str


class DecisionLaneOutput(TypedDict):
    decision_lane: str
    reason: str
    human_review_required: bool
    non_claim: str


class MarketContextOutput(TypedDict):
    market_context_status: str
    context_label: str
    context_notes: list[str]
    live_context_enabled: bool
    non_claim: str


class CalibrationOutput(TypedDict):
    calibrated_confidence: float
    calibration_policy: str
    fine_tuning_performed: bool
    explanation: str


class ReviewCycleOutput(TypedDict):
    cycle_mode: str
    layers_completed: list[str]
    non_realtime_claim: str
    timestamp: str


class PortfolioDiagnosticAllocatorOutput(TypedDict):
    allocation_view: str
    max_research_weight: float
    allocation_is_advisory: bool
    explanation: str
    non_claim: str


class PhaseRouterOutput(TypedDict):
    route: str
    dashboard_status: str
    human_review_required: bool
    explanation: str
    non_claim: str


@dataclass(frozen=True)
class DiagnosticChainOutput:
    ticker: str
    layer_1_quant_core: QuantCoreOutput
    layer_2_scenario: ScenarioOutput
    layer_3_risk_governance: RiskGovernanceOutput
    layer_4_decision_lane: DecisionLaneOutput
    layer_5_market_context: MarketContextOutput
    layer_6_calibration: CalibrationOutput
    review_cycle: ReviewCycleOutput
    layer_7_portfolio_diagnostic_allocator: PortfolioDiagnosticAllocatorOutput
    layer_8_phase_router: PhaseRouterOutput
    non_claim: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _walk_values(obj: Any):
    if is_dataclass(obj) and not isinstance(obj, type):
        yield from _walk_values(asdict(obj))
    elif isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key)
            yield from _walk_values(value)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for value in obj:
            yield from _walk_values(value)
    elif isinstance(obj, str):
        yield obj


def _contains_forbidden_public_term(text: str, term: str) -> bool:
    normalized = term.lower()
    if " " in normalized:
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in normalized.split()) + r"\b"
    else:
        pattern = rf"\b{re.escape(normalized)}\b"
    return re.search(pattern, text.lower()) is not None


def assert_no_forbidden_public_terms(obj: Any) -> None:
    """Fail if public diagnostic output uses prohibited action-oriented wording."""

    for text in _walk_values(obj):
        for term in FORBIDDEN_PUBLIC_TERMS:
            if _contains_forbidden_public_term(text, term):
                raise ValueError(f"forbidden public wording detected: {term}")


def assert_allowed(value: str, allowed: frozenset[str], field_name: str) -> None:
    if value not in allowed:
        raise ValueError(f"unsupported {field_name}: {value}")
