"""Registry for metadata-only non-QML diagnostic adapters."""

from __future__ import annotations

from importlib import import_module

from .base import BaseDiagnosticAdapter
from .inventory import ALLOWED_MODEL_FAMILIES, EXCLUDED_FROM_MVP, MODEL_INVENTORY


def _contains_excluded_token(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in EXCLUDED_FROM_MVP)


def _validate_adapter(adapter: BaseDiagnosticAdapter) -> None:
    if not adapter.model_key:
        raise ValueError("adapter model_key is required")
    if _contains_excluded_token(adapter.model_key) or _contains_excluded_token(adapter.model_family):
        raise ValueError(f"excluded model family or key: {adapter.model_key}")
    if adapter.model_family not in ALLOWED_MODEL_FAMILIES:
        raise ValueError(f"unsupported model family for {adapter.model_key}: {adapter.model_family}")


def _load_adapter(entry: dict[str, object]) -> BaseDiagnosticAdapter:
    model_key = str(entry["model_key"])
    model_family = str(entry["model_family"])
    class_name = str(entry["adapter_class"])
    module = import_module(f".{model_family}.{model_key}_diagnostic", package=__package__)
    adapter_class = getattr(module, class_name)
    if not issubclass(adapter_class, BaseDiagnosticAdapter):
        raise TypeError(f"{class_name} must inherit BaseDiagnosticAdapter")
    adapter = adapter_class()
    _validate_adapter(adapter)
    return adapter


def _build_registry() -> dict[str, BaseDiagnosticAdapter]:
    registry: dict[str, BaseDiagnosticAdapter] = {}
    for entry in MODEL_INVENTORY:
        adapter = _load_adapter(entry)
        if adapter.model_key in registry:
            raise ValueError(f"duplicate model_key registered: {adapter.model_key}")
        registry[adapter.model_key] = adapter
    return registry


_REGISTRY = _build_registry()


def get_adapter(model_key: str) -> BaseDiagnosticAdapter:
    if _contains_excluded_token(model_key):
        raise KeyError(f"excluded model key: {model_key}")
    return _REGISTRY[model_key]


def list_adapters() -> tuple[BaseDiagnosticAdapter, ...]:
    return tuple(_REGISTRY[key] for key in sorted(_REGISTRY))


def list_by_family(model_family: str) -> tuple[BaseDiagnosticAdapter, ...]:
    if _contains_excluded_token(model_family) or model_family not in ALLOWED_MODEL_FAMILIES:
        raise ValueError(f"unsupported model family: {model_family}")
    return tuple(adapter for adapter in list_adapters() if adapter.model_family == model_family)


def list_exploratory() -> tuple[BaseDiagnosticAdapter, ...]:
    return tuple(adapter for adapter in list_adapters() if adapter.is_exploratory)


def list_missing_dependency() -> tuple[BaseDiagnosticAdapter, ...]:
    return tuple(
        adapter
        for adapter in list_adapters()
        if adapter.dependency_status in {"missing_dependency", "optional_dependency"}
    )
