"""Generate stack engine specs for governed static MVP combinations."""

from __future__ import annotations

from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec

from .catalog_schema import (
    DEPENDENCY_POLICIES,
    FEATURE_SETS,
    HORIZONS,
    RUN_MODE,
    SELECTION_POLICIES,
    SPLIT_POLICY,
    STACK_TYPES,
    TARGETS,
    sorted_specs,
)


def _stack_spec(
    stack_type: str,
    target: str,
    horizon: int,
    feature_set: str,
    selection_policy: str,
    dependency_policy: str,
) -> EngineSpec:
    selection_segment = f"{selection_policy}_{dependency_policy}"
    engine_id = f"stack.{stack_type}.{target}.h{horizon}.{feature_set}.{selection_segment}"
    return EngineSpec(
        engine_id=engine_id,
        engine_type="stack",
        model_key=None,
        model_family="ensemble_regime",
        target=target,
        horizon=horizon,
        feature_set=feature_set,
        policy=dependency_policy,
        split_policy=SPLIT_POLICY,
        run_mode=RUN_MODE,
        dependencies=(f"support.evidence_strength.static_demo.{target}.h{horizon}.{feature_set}_classification",),
        claim_scope="exploratory_only",
        metadata={
            "source": "generated_stack_catalog",
            "stack_type": stack_type,
            "selection_policy": selection_policy,
            "dependency_policy": dependency_policy,
            "requires_dependency_outputs": True,
        },
    )


def generate_stack_catalog() -> tuple[EngineSpec, ...]:
    specs: list[EngineSpec] = []
    for stack_type in STACK_TYPES:
        for target in TARGETS:
            for horizon in HORIZONS:
                for feature_set in FEATURE_SETS:
                    for selection_policy in SELECTION_POLICIES:
                        for dependency_policy in DEPENDENCY_POLICIES:
                            specs.append(
                                _stack_spec(
                                    stack_type,
                                    target,
                                    horizon,
                                    feature_set,
                                    selection_policy,
                                    dependency_policy,
                                )
                            )
    return sorted_specs(specs)
