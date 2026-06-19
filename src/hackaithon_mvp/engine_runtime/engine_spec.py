"""EngineSpec contract for generated HackAIthon MVP engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.hackaithon_mvp.timeframe_schema import normalize_timeframe

from .engine_id import EngineIdValidationError, assert_no_forbidden_terms, validate_engine_id


ALLOWED_ENGINE_TYPES = frozenset({"baseline", "support", "stack"})
ALLOWED_RUN_MODES = frozenset({"static_evidence_mvp"})
ALLOWED_CLAIM_SCOPES = frozenset({"diagnostic_only", "exploratory_only", "evidence_insufficient"})


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _walk_strings(item)


@dataclass(frozen=True)
class EngineSpec:
    """A generated runnable diagnostic engine specification."""

    engine_id: str
    engine_type: str
    model_key: str | None
    model_family: str | None
    target: str
    horizon: int
    feature_set: str
    policy: str
    split_policy: str
    run_mode: str
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    claim_scope: str = "diagnostic_only"
    metadata: dict[str, Any] = field(default_factory=dict)
    timeframe: str | None = None

    def __post_init__(self) -> None:
        parsed_type = validate_engine_id(self.engine_id)
        if self.engine_type not in ALLOWED_ENGINE_TYPES:
            raise ValueError(f"unsupported engine_type: {self.engine_type}")
        if parsed_type != self.engine_type:
            raise ValueError(f"engine_id type {parsed_type} does not match engine_type {self.engine_type}")
        if self.run_mode not in ALLOWED_RUN_MODES:
            raise ValueError(f"unsupported run_mode: {self.run_mode}")
        if self.claim_scope not in ALLOWED_CLAIM_SCOPES:
            raise ValueError(f"unsupported claim_scope: {self.claim_scope}")
        if not isinstance(self.horizon, int) or self.horizon <= 0:
            raise ValueError("horizon must be a positive integer")
        if self.engine_type == "baseline" and (not self.model_key or not self.model_family):
            raise ValueError("baseline specs require model_key and model_family")
        if not isinstance(self.dependencies, tuple):
            object.__setattr__(self, "dependencies", tuple(self.dependencies))
        if self.timeframe is not None:
            object.__setattr__(self, "timeframe", normalize_timeframe(str(self.timeframe)))
        metadata = dict(self.metadata)
        if "timeframe" in metadata and metadata["timeframe"] is not None:
            metadata["timeframe"] = normalize_timeframe(str(metadata["timeframe"]))
            object.__setattr__(self, "metadata", metadata)
        for field_name in ("model_key", "model_family", "target", "feature_set", "policy", "split_policy"):
            value = getattr(self, field_name)
            if value is not None:
                assert_no_forbidden_terms(value, field_name=field_name)
        for index, dependency in enumerate(self.dependencies):
            assert_no_forbidden_terms(dependency, field_name=f"dependencies[{index}]")
        for text in _walk_strings(self.metadata):
            assert_no_forbidden_terms(text, field_name="metadata")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "engine_id": self.engine_id,
            "engine_type": self.engine_type,
            "model_key": self.model_key,
            "model_family": self.model_family,
            "target": self.target,
            "horizon": self.horizon,
            "feature_set": self.feature_set,
            "policy": self.policy,
            "split_policy": self.split_policy,
            "run_mode": self.run_mode,
            "dependencies": list(self.dependencies),
            "claim_scope": self.claim_scope,
            "metadata": self.metadata,
        }
        if self.timeframe is not None:
            payload["timeframe"] = self.timeframe
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EngineSpec":
        try:
            values = dict(payload)
            values["dependencies"] = tuple(values.get("dependencies", ()))
            return cls(**values)
        except EngineIdValidationError:
            raise
        except TypeError as exc:
            raise ValueError(f"invalid EngineSpec payload: {exc}") from exc
