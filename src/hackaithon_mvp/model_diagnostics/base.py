"""Base contract for HackAIthon MVP model diagnostics.

This layer is metadata-only. It has no methods for model execution.
"""

from __future__ import annotations

from typing import Any, ClassVar


FAMILY_CONSTRAINTS: dict[str, str] = {
    "baseline": "Static baseline metadata for local historical comparison review.",
    "classification": "Static classifier metadata for local historical direction review.",
    "regression": "Static return and price metadata for local historical review.",
    "statistical": "Static time-series metadata for local historical review.",
    "ensemble_regime": "Static ensemble and regime metadata for local historical review.",
    "deep_learning": "Static sequence-model metadata for local historical review.",
}


class BaseDiagnosticAdapter:
    """Metadata contract shared by all MVP diagnostic adapters."""

    model_key: ClassVar[str]
    display_name: ClassVar[str]
    model_family: ClassVar[str]
    supported_targets: ClassVar[tuple[str, ...]] = ()
    supported_horizons: ClassVar[tuple[int, ...]] = ()
    diagnostic_scope: ClassVar[str] = "Static local historical metadata review."
    is_exploratory: ClassVar[bool] = False
    dependency_status: ClassVar[str] = "not_required_for_static_mvp"
    source_paths: ClassVar[tuple[str, ...]] = ()

    def summarize_family_constraints(self) -> str:
        return FAMILY_CONSTRAINTS.get(self.model_family, "Static local historical metadata review.")

    def to_metadata(self) -> dict[str, Any]:
        return {
            "model_key": self.model_key,
            "display_name": self.display_name,
            "model_family": self.model_family,
            "supported_targets": list(self.supported_targets),
            "supported_horizons": list(self.supported_horizons),
            "diagnostic_scope": self.diagnostic_scope,
            "is_exploratory": self.is_exploratory,
            "dependency_status": self.dependency_status,
            "source_paths": list(self.source_paths),
            "family_constraints": self.summarize_family_constraints(),
        }
