"""Dependency helpers for MVP support and stack engines."""

from __future__ import annotations

from collections.abc import Mapping

from .engine_result import EngineResult
from .engine_spec import EngineSpec


DependencyResults = Mapping[str, EngineResult | dict[str, object]]


def available_dependency_ids(dependency_results: DependencyResults | None) -> set[str]:
    if not dependency_results:
        return set()
    return set(dependency_results)


def missing_dependencies(spec: EngineSpec, dependency_results: DependencyResults | None) -> tuple[str, ...]:
    if spec.engine_type == "baseline":
        return ()
    available = available_dependency_ids(dependency_results)
    if not spec.dependencies:
        return ("dependency_outputs",)
    return tuple(dependency for dependency in spec.dependencies if dependency not in available)


def dependency_lineage(spec: EngineSpec, dependency_results: DependencyResults | None) -> tuple[str, ...]:
    available = available_dependency_ids(dependency_results)
    return tuple(dependency for dependency in spec.dependencies if dependency in available)
