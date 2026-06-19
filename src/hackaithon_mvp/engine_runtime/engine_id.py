"""Deterministic engine ID validation."""

from __future__ import annotations

import re


BASELINE_ENGINE_RE = re.compile(
    r"^(?P<family>[a-z][a-z0-9_]*)\."
    r"(?P<model_key>[a-z][a-z0-9_]*)\."
    r"(?P<target>[a-z][a-z0-9_]*)\."
    r"h(?P<horizon>[1-9][0-9]*)\."
    r"(?P<feature_set>[a-z][a-z0-9_]*)\."
    r"(?P<policy>[a-z][a-z0-9_]*)$"
)
SUPPORT_ENGINE_RE = re.compile(
    r"^support\."
    r"(?P<support_type>[a-z][a-z0-9_]*)\."
    r"(?P<universe>[a-z][a-z0-9_]*)\."
    r"(?P<target>[a-z][a-z0-9_]*)\."
    r"h(?P<horizon>[1-9][0-9]*)\."
    r"(?P<scope>[a-z][a-z0-9_]*)$"
)
STACK_ENGINE_RE = re.compile(
    r"^stack\."
    r"(?P<stack_type>[a-z][a-z0-9_]*)\."
    r"(?P<target>[a-z][a-z0-9_]*)\."
    r"h(?P<horizon>[1-9][0-9]*)\."
    r"(?P<feature_set>[a-z][a-z0-9_]*)\."
    r"(?P<selection_policy>[a-z][a-z0-9_]*)$"
)

FORBIDDEN_SUBSTRINGS = ("qml", "quantum")
FORBIDDEN_TERMS = ("buy", "sell", "hold", "trade", "trading", "recommendation", "allocation", "advice")
FORBIDDEN_PHRASES = ("allocation_advice",)


class EngineIdValidationError(ValueError):
    """Raised when an engine ID is not deterministic or scope safe."""


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def contains_forbidden_term(value: object) -> bool:
    text = str(value).lower()
    if any(term in text for term in FORBIDDEN_SUBSTRINGS):
        return True
    if any(phrase in text for phrase in FORBIDDEN_PHRASES):
        return True
    tokens = _tokens(text)
    return any(term in tokens for term in FORBIDDEN_TERMS)


def assert_no_forbidden_terms(value: object, *, field_name: str = "value") -> None:
    if contains_forbidden_term(value):
        raise EngineIdValidationError(f"{field_name} contains an excluded term")


def validate_engine_id(engine_id: str) -> str:
    """Validate an engine ID and return its engine type."""

    if not isinstance(engine_id, str) or not engine_id:
        raise EngineIdValidationError("engine_id must be a non-empty string")
    assert_no_forbidden_terms(engine_id, field_name="engine_id")

    if SUPPORT_ENGINE_RE.fullmatch(engine_id):
        return "support"
    if STACK_ENGINE_RE.fullmatch(engine_id):
        return "stack"
    if BASELINE_ENGINE_RE.fullmatch(engine_id):
        return "baseline"
    raise EngineIdValidationError(f"invalid engine_id format: {engine_id}")
