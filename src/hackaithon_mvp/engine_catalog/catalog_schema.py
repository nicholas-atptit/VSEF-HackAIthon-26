"""Shared catalog dimensions and serialization helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_DIR = REPO_ROOT / "catalogs" / "hackaithon_mvp"

TARGETS = ("absolute_direction", "return_direction", "forward_return", "volatility_adjusted_return", "market_relative_direction")
HORIZONS = (1, 5, 10, 20, 40)
FEATURE_SETS = ("basic", "technical", "market_context", "relative_strength", "volatility", "feature_set_c")
POLICIES = ("default", "validation_only", "threshold_050", "threshold_055", "calibrated")
SPLIT_POLICY = "validation_final_locked"
RUN_MODE = "static_evidence_mvp"

SUPPORT_TYPES = (
    "model_disagreement",
    "baseline_edge",
    "class_balance",
    "drift_risk",
    "liquidity_risk",
    "regime_instability",
    "evidence_strength",
    "scope_mismatch",
    "overfit_pressure",
    "final_window_selection_risk",
)
UNIVERSES = ("vn30", "vn100", "static_demo")
FEATURE_SCOPES = ("basic_scope", "technical_scope", "market_context_scope", "relative_strength_scope", "volatility_scope")
SUPPORT_MODEL_FAMILIES = ("baseline", "classification", "regression", "statistical", "deep_learning", "ensemble_regime")

STACK_TYPES = (
    "validation_topk_vote",
    "validation_topk_weighted_vote",
    "family_diverse_vote",
    "risk_adjusted_vote",
    "scenario_weighted_vote",
    "baseline_gated_stack",
    "regime_conditional_stack",
    "confidence_weighted_stack",
    "rank_average_stack",
    "probability_average_stack",
)
SELECTION_POLICIES = ("validation_top3", "validation_top5", "family_diverse", "risk_adjusted", "baseline_gated")
DEPENDENCY_POLICIES = ("requires_baseline_outputs", "requires_support_outputs", "requires_baseline_and_support_outputs")

DIRECTION_TARGETS = frozenset({"absolute_direction", "return_direction", "market_relative_direction"})
RETURN_TARGETS = frozenset({"forward_return", "volatility_adjusted_return"})


def sorted_specs(specs: Iterable[EngineSpec]) -> tuple[EngineSpec, ...]:
    return tuple(sorted(specs, key=lambda spec: spec.engine_id))


def spec_to_json_line(spec: EngineSpec) -> str:
    return json.dumps(spec.to_dict(), sort_keys=True)
