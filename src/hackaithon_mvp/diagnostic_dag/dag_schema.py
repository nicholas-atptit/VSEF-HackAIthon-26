"""Schema helpers for the local diagnostic DAG runtime."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from src.hackaithon_mvp.timeframe_schema import normalize_timeframe


ALLOWED_EXECUTION_MODES = frozenset({"static_local", "contract_only", "optional"})
REQUIRED_CLAIM_BOUNDARY = {
    "no_live_data": True,
    "no_provider_calls": True,
    "no_training": True,
    "no_inference": True,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Research diagnostic only; static local evidence boundary applies."
FORBIDDEN_PUBLIC_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\bstrong\s+buy\b",
    r"\bstrong\s+sell\b",
    r"\brecommendation\b",
    r"\btrading\s+signal\b",
    r"\binvestment\s+advice\b",
    r"\bfinancial\s+advice\b",
    r"\bportfolio\s+allocation\s+advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bsupport(?:ed|s|ing)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bdeployment\b",
    r"\bapproval\b",
    r"\bclient\s+relationship\b",
)


def _tuple_of_strings(values: tuple[str, ...] | list[str] | None, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be a tuple or list")
    return tuple(str(value).strip() for value in values if str(value).strip())


def _walk_values(value: Any):
    if is_dataclass(value) and not isinstance(value, type):
        yield from _walk_values(asdict(value))
    elif isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _walk_values(nested)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            yield from _walk_values(nested)
    elif isinstance(value, str):
        yield value


def forbidden_public_patterns(payload: Any) -> list[str]:
    """Return forbidden public wording regexes found in a JSON-compatible payload."""

    matches: list[str] = []
    for text in _walk_values(payload):
        lowered = text.lower()
        for pattern in FORBIDDEN_PUBLIC_PATTERNS:
            if re.search(pattern, lowered) and pattern not in matches:
                matches.append(pattern)
    return matches


def assert_no_forbidden_public_terms(payload: Any) -> None:
    matches = forbidden_public_patterns(payload)
    if matches:
        raise ValueError(f"forbidden public wording found: {', '.join(matches)}")


def claim_boundary() -> dict[str, bool]:
    return dict(REQUIRED_CLAIM_BOUNDARY)


def validate_claim_boundary_flags(value: Any) -> list[str]:
    boundary = value if isinstance(value, dict) else {}
    errors: list[str] = []
    for key, expected in REQUIRED_CLAIM_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"claim_boundary.{key} must be {expected}")
    return errors


def deterministic_run_id(*, ticker: str, timeframe: str, horizon_steps: int, policy_id: str | None = None) -> str:
    key = "|".join((ticker.strip().upper(), normalize_timeframe(timeframe), str(int(horizon_steps)), policy_id or "none"))
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"dag-{digest}"


@dataclass(frozen=True)
class DAGNodeSpec:
    node_id: str
    node_name: str
    layer: str
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    required_inputs: tuple[str, ...] = field(default_factory=tuple)
    optional_inputs: tuple[str, ...] = field(default_factory=tuple)
    produces: tuple[str, ...] = field(default_factory=tuple)
    is_required: bool = True
    execution_mode: str = "static_local"
    claim_boundary: dict[str, bool] = field(default_factory=claim_boundary)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.node_id).strip():
            raise ValueError("node_id must be non-empty")
        if not str(self.node_name).strip():
            raise ValueError("node_name must be non-empty")
        if not str(self.layer).strip():
            raise ValueError("layer must be non-empty")
        object.__setattr__(self, "node_id", str(self.node_id).strip())
        object.__setattr__(self, "node_name", str(self.node_name).strip())
        object.__setattr__(self, "layer", str(self.layer).strip())
        object.__setattr__(self, "depends_on", _tuple_of_strings(self.depends_on, "depends_on"))
        object.__setattr__(self, "required_inputs", _tuple_of_strings(self.required_inputs, "required_inputs"))
        object.__setattr__(self, "optional_inputs", _tuple_of_strings(self.optional_inputs, "optional_inputs"))
        object.__setattr__(self, "produces", _tuple_of_strings(self.produces, "produces"))
        if self.execution_mode not in ALLOWED_EXECUTION_MODES:
            raise ValueError(f"unsupported execution_mode: {self.execution_mode}")
        errors = validate_claim_boundary_flags(self.claim_boundary)
        if errors:
            raise ValueError("; ".join(errors))
        assert_no_forbidden_public_terms(
            {
                "node_id": self.node_id,
                "node_name": self.node_name,
                "layer": self.layer,
                "metadata": self.metadata,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("depends_on", "required_inputs", "optional_inputs", "produces"):
            payload[key] = list(payload[key])
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DAGNodeSpec":
        return cls(**dict(payload))


@dataclass(frozen=True)
class DAGExecutionContext:
    ticker: str
    timeframe: str
    horizon_steps: int
    run_id: str | None = None
    policy_id: str | None = None
    policy_name: str | None = None
    static_inputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ticker = str(self.ticker).strip().upper()
        if not ticker:
            raise ValueError("ticker must be non-empty")
        timeframe = normalize_timeframe(str(self.timeframe))
        horizon_steps = int(self.horizon_steps)
        if horizon_steps <= 0:
            raise ValueError("horizon_steps must be positive")
        run_id = str(self.run_id).strip() if self.run_id else deterministic_run_id(
            ticker=ticker,
            timeframe=timeframe,
            horizon_steps=horizon_steps,
            policy_id=self.policy_id,
        )
        object.__setattr__(self, "ticker", ticker)
        object.__setattr__(self, "timeframe", timeframe)
        object.__setattr__(self, "horizon_steps", horizon_steps)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "static_inputs", dict(self.static_inputs or {}))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DAGExecutionContext":
        return cls(**dict(payload))


@dataclass(frozen=True)
class DAGNodeResult:
    node_id: str
    status: str
    outputs: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None
    claim_boundary: dict[str, bool] = field(default_factory=claim_boundary)
    non_claim: str = NON_CLAIM_TEXT

    def __post_init__(self) -> None:
        if self.status not in {"completed", "skipped", "failed"}:
            raise ValueError(f"unsupported node result status: {self.status}")
        object.__setattr__(self, "warnings", _tuple_of_strings(self.warnings, "warnings"))
        errors = validate_claim_boundary_flags(self.claim_boundary)
        if errors:
            raise ValueError("; ".join(errors))
        assert_no_forbidden_public_terms(
            {
                "node_id": self.node_id,
                "status": self.status,
                "outputs": self.outputs,
                "warnings": self.warnings,
                "error": self.error,
                "non_claim": self.non_claim,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class DAGExecutionResult:
    run_id: str
    ticker: str
    timeframe: str
    horizon_steps: int
    dag_valid: bool
    execution_status: str
    topological_order: tuple[str, ...]
    node_results: list[dict[str, Any]]
    final_state: dict[str, Any]
    audit_trail: list[dict[str, Any]]
    claim_boundary: dict[str, bool] = field(default_factory=claim_boundary)
    non_claim: str = NON_CLAIM_TEXT

    def __post_init__(self) -> None:
        if self.execution_status not in {"completed", "completed_with_warnings", "failed"}:
            raise ValueError(f"unsupported execution_status: {self.execution_status}")
        object.__setattr__(self, "topological_order", _tuple_of_strings(self.topological_order, "topological_order"))
        errors = validate_claim_boundary_flags(self.claim_boundary)
        if errors:
            raise ValueError("; ".join(errors))
        assert_no_forbidden_public_terms(
            {
                "execution_status": self.execution_status,
                "final_state": self.final_state,
                "audit_trail": self.audit_trail,
                "non_claim": self.non_claim,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["topological_order"] = list(self.topological_order)
        return payload
