"""Generate baseline engine specs from non-QML metadata adapters."""

from __future__ import annotations

from src.hackaithon_mvp.engine_runtime.engine_id import contains_forbidden_term
from src.hackaithon_mvp.engine_runtime.engine_spec import EngineSpec
from src.hackaithon_mvp.model_diagnostics.base import BaseDiagnosticAdapter
from src.hackaithon_mvp.model_diagnostics.registry import list_adapters

from .catalog_schema import (
    DIRECTION_TARGETS,
    FEATURE_SETS,
    HORIZONS,
    POLICIES,
    RETURN_TARGETS,
    RUN_MODE,
    SPLIT_POLICY,
    TARGETS,
    sorted_specs,
)


PRIMITIVE_ENSEMBLE_KEYS = frozenset({"regime_context_logistic", "regime_context_lightgbm", "regime_context_xgboost"})


def _target_is_compatible(adapter: BaseDiagnosticAdapter, target: str) -> bool:
    family = adapter.model_family
    if family in {"baseline", "classification", "deep_learning"}:
        return target in DIRECTION_TARGETS
    if family == "regression":
        return target in RETURN_TARGETS
    if family == "statistical":
        return target in DIRECTION_TARGETS.union(RETURN_TARGETS)
    if family == "ensemble_regime":
        return adapter.model_key in PRIMITIVE_ENSEMBLE_KEYS and target in DIRECTION_TARGETS
    return False


def _claim_scope(adapter: BaseDiagnosticAdapter) -> str:
    if adapter.is_exploratory or adapter.model_family in {"deep_learning", "statistical"}:
        return "exploratory_only"
    return "diagnostic_only"


def _dependency_note(adapter: BaseDiagnosticAdapter) -> str:
    if adapter.model_family == "deep_learning":
        return "optional_or_missing_dependency_not_required_for_static_mvp"
    return adapter.dependency_status


def _baseline_spec(adapter: BaseDiagnosticAdapter, target: str, horizon: int, feature_set: str, policy: str) -> EngineSpec:
    engine_id = f"{adapter.model_family}.{adapter.model_key}.{target}.h{horizon}.{feature_set}.{policy}"
    return EngineSpec(
        engine_id=engine_id,
        engine_type="baseline",
        model_key=adapter.model_key,
        model_family=adapter.model_family,
        target=target,
        horizon=horizon,
        feature_set=feature_set,
        policy=policy,
        split_policy=SPLIT_POLICY,
        run_mode=RUN_MODE,
        dependencies=(),
        claim_scope=_claim_scope(adapter),
        metadata={
            "source": "generated_from_mvp_model_adapter",
            "adapter_dependency_status": _dependency_note(adapter),
            "adapter_display_name": adapter.display_name,
            "metadata_only_static_mvp": True,
            "training_enabled": False,
            "inference_enabled": False,
            "provider_access_enabled": False,
        },
    )


def generate_baseline_catalog() -> tuple[EngineSpec, ...]:
    specs: list[EngineSpec] = []
    for adapter in list_adapters():
        if contains_forbidden_term(adapter.model_key) or contains_forbidden_term(adapter.model_family):
            continue
        for target in TARGETS:
            if not _target_is_compatible(adapter, target):
                continue
            for horizon in HORIZONS:
                for feature_set in FEATURE_SETS:
                    for policy in POLICIES:
                        specs.append(_baseline_spec(adapter, target, horizon, feature_set, policy))
    return sorted_specs(specs)
