"""Generate support engine specs for static MVP dependency diagnostics."""

from __future__ import annotations

from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec

from .catalog_schema import (
    FEATURE_SCOPES,
    HORIZONS,
    RUN_MODE,
    SPLIT_POLICY,
    SUPPORT_MODEL_FAMILIES,
    SUPPORT_TYPES,
    TARGETS,
    UNIVERSES,
    sorted_specs,
)


def _support_spec(
    support_type: str,
    universe: str,
    target: str,
    horizon: int,
    feature_scope: str,
    model_family: str,
) -> EngineSpec:
    scope = f"{feature_scope}_{model_family}"
    return EngineSpec(
        engine_id=f"support.{support_type}.{universe}.{target}.h{horizon}.{scope}",
        engine_type="support",
        model_key=None,
        model_family=model_family,
        target=target,
        horizon=horizon,
        feature_set=feature_scope,
        policy=support_type,
        split_policy=SPLIT_POLICY,
        run_mode=RUN_MODE,
        dependencies=(f"{model_family}.{target}.h{horizon}.{feature_scope}",),
        claim_scope="diagnostic_only",
        metadata={
            "source": "generated_support_catalog",
            "support_type": support_type,
            "universe": universe,
            "scope": scope,
            "requires_dependency_outputs": True,
        },
    )


def generate_support_catalog() -> tuple[EngineSpec, ...]:
    specs = [
        _support_spec(support_type, universe, target, horizon, feature_scope, model_family)
        for support_type in SUPPORT_TYPES
        for universe in UNIVERSES
        for target in TARGETS
        for horizon in HORIZONS
        for feature_scope in FEATURE_SCOPES
        for model_family in SUPPORT_MODEL_FAMILIES
    ]
    return sorted_specs(specs)
