"""EngineResult contract for static MVP engine runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .engine_id import assert_no_forbidden_terms, validate_engine_id
from .engine_spec import ALLOWED_CLAIM_SCOPES, _walk_strings


ALLOWED_STATUSES = frozenset(
    {
        "completed",
        "skipped_missing_dependency",
        "skipped_missing_evidence",
        "failed_validation",
        "blocked_by_claim_boundary",
    }
)
ALLOWED_DIAGNOSTIC_LABELS = frozenset(
    {
        "positive_bias",
        "negative_bias",
        "neutral_or_uncertain",
        "insufficient_evidence",
        "exploratory_only",
    }
)
DEFAULT_NON_CLAIM = "Research diagnostic only; static MVP evidence boundary applies."


@dataclass(frozen=True)
class EngineResult:
    """Result artifact emitted by one static MVP engine run."""

    engine_id: str
    status: str
    diagnostic_label: str
    confidence: float | None
    risk_flags: tuple[str, ...] = field(default_factory=tuple)
    metrics: dict[str, Any] = field(default_factory=dict)
    dependencies_used: tuple[str, ...] = field(default_factory=tuple)
    claim_scope: str = "diagnostic_only"
    non_claim: str = DEFAULT_NON_CLAIM
    warnings: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_engine_id(self.engine_id)
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"unsupported status: {self.status}")
        if self.diagnostic_label not in ALLOWED_DIAGNOSTIC_LABELS:
            raise ValueError(f"unsupported diagnostic_label: {self.diagnostic_label}")
        if self.claim_scope not in ALLOWED_CLAIM_SCOPES:
            raise ValueError(f"unsupported claim_scope: {self.claim_scope}")
        if self.confidence is not None and not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1 when provided")
        for attr in ("risk_flags", "dependencies_used", "warnings"):
            value = getattr(self, attr)
            if not isinstance(value, tuple):
                object.__setattr__(self, attr, tuple(value))
        for field_name in ("non_claim",):
            assert_no_forbidden_terms(getattr(self, field_name), field_name=field_name)
        for index, value in enumerate(self.risk_flags):
            assert_no_forbidden_terms(value, field_name=f"risk_flags[{index}]")
        for index, value in enumerate(self.dependencies_used):
            assert_no_forbidden_terms(value, field_name=f"dependencies_used[{index}]")
        for index, value in enumerate(self.warnings):
            assert_no_forbidden_terms(value, field_name=f"warnings[{index}]")
        for text in _walk_strings(self.metrics):
            assert_no_forbidden_terms(text, field_name="metrics")
        for text in _walk_strings(self.metadata):
            assert_no_forbidden_terms(text, field_name="metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "status": self.status,
            "diagnostic_label": self.diagnostic_label,
            "confidence": self.confidence,
            "risk_flags": list(self.risk_flags),
            "metrics": self.metrics,
            "dependencies_used": list(self.dependencies_used),
            "claim_scope": self.claim_scope,
            "non_claim": self.non_claim,
            "warnings": list(self.warnings),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EngineResult":
        values = dict(payload)
        for attr in ("risk_flags", "dependencies_used", "warnings"):
            values[attr] = tuple(values.get(attr, ()))
        return cls(**values)
