"""Validation and topological sorting for diagnostic DAG nodes."""

from __future__ import annotations

from collections import deque
from typing import Any

from .dag_registry import DEFAULT_DAG_NODE_IDS
from .dag_schema import NON_CLAIM_TEXT, forbidden_public_patterns, validate_claim_boundary_flags


def _node_ids(nodes: tuple[dict, ...]) -> list[str]:
    return [str(node.get("node_id", "")).strip() for node in nodes]


def _dependency_map(nodes: tuple[dict, ...]) -> dict[str, tuple[str, ...]]:
    return {
        str(node.get("node_id", "")).strip(): tuple(str(dep).strip() for dep in (node.get("depends_on") or ()))
        for node in nodes
    }


def detect_cycles(nodes: tuple[dict, ...]) -> dict:
    """Detect dependency cycles with deterministic traversal."""

    dependencies = _dependency_map(nodes)
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: list[list[str]] = []

    def visit(node_id: str, path: list[str]) -> None:
        if node_id in visiting:
            start = path.index(node_id) if node_id in path else 0
            cycles.append(path[start:] + [node_id])
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency in dependencies.get(node_id, ()):
            if dependency in dependencies:
                visit(dependency, path + [dependency])
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in _node_ids(nodes):
        if node_id:
            visit(node_id, [node_id])
    return {"has_cycle": bool(cycles), "cycles": cycles}


def topological_sort(nodes: tuple[dict, ...]) -> tuple[str, ...]:
    """Return deterministic topological order for a valid DAG."""

    ids = _node_ids(nodes)
    id_set = set(ids)
    if len(ids) != len(id_set):
        duplicates = sorted({node_id for node_id in ids if ids.count(node_id) > 1})
        raise ValueError(f"duplicate node IDs: {duplicates}")
    missing = sorted(
        {
            dependency
            for node in nodes
            for dependency in (str(dep).strip() for dep in (node.get("depends_on") or ()))
            if dependency not in id_set
        }
    )
    if missing:
        raise ValueError(f"missing dependencies: {missing}")
    cycle_result = detect_cycles(nodes)
    if cycle_result["has_cycle"]:
        raise ValueError(f"cycle detected: {cycle_result['cycles']}")

    dependents: dict[str, list[str]] = {node_id: [] for node_id in ids}
    indegree: dict[str, int] = {node_id: 0 for node_id in ids}
    position = {node_id: index for index, node_id in enumerate(ids)}
    for node in nodes:
        node_id = str(node.get("node_id")).strip()
        for dependency in (str(dep).strip() for dep in (node.get("depends_on") or ())):
            dependents[dependency].append(node_id)
            indegree[node_id] += 1
    ready = deque(sorted((node_id for node_id, degree in indegree.items() if degree == 0), key=position.get))
    order: list[str] = []
    while ready:
        node_id = ready.popleft()
        order.append(node_id)
        for dependent in sorted(dependents[node_id], key=position.get):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    if len(order) != len(nodes):
        raise ValueError("topological order did not include all nodes")
    return tuple(order)


def _validate_required_nodes(ids: set[str]) -> list[str]:
    if not ids.intersection(DEFAULT_DAG_NODE_IDS):
        return []
    return [f"required node missing: {node_id}" for node_id in DEFAULT_DAG_NODE_IDS if node_id not in ids]


def _validate_node_shape(node: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    node_id = str(node.get("node_id", "")).strip() or "<missing>"
    for field in ("node_id", "node_name", "layer", "depends_on", "required_inputs", "optional_inputs", "produces"):
        if field not in node:
            errors.append(f"{node_id}: missing field {field}")
    if node.get("execution_mode") not in {"static_local", "contract_only", "optional"}:
        errors.append(f"{node_id}: unsupported execution_mode {node.get('execution_mode')}")
    for boundary_error in validate_claim_boundary_flags(node.get("claim_boundary")):
        errors.append(f"{node_id}: {boundary_error}")
    forbidden = forbidden_public_patterns(
        {
            "node_id": node.get("node_id"),
            "node_name": node.get("node_name"),
            "layer": node.get("layer"),
            "metadata": node.get("metadata", {}),
        }
    )
    if forbidden:
        errors.append(f"{node_id}: forbidden public wording found: {', '.join(forbidden)}")
    return errors


def validate_dag(nodes: tuple[dict, ...]) -> dict:
    """Validate DAG node registry and return a JSON-compatible result."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(nodes, tuple):
        errors.append("nodes must be a tuple")
        nodes = tuple(nodes) if isinstance(nodes, list) else ()
    ids = _node_ids(nodes)
    id_set = set(ids)
    if any(not node_id for node_id in ids):
        errors.append("node_id must be non-empty")
    duplicates = sorted({node_id for node_id in ids if ids.count(node_id) > 1})
    if duplicates:
        errors.append(f"duplicate node IDs: {duplicates}")
    errors.extend(_validate_required_nodes(id_set))
    for node in nodes:
        if not isinstance(node, dict):
            errors.append("each node must be a dictionary")
            continue
        errors.extend(_validate_node_shape(node))
        for dependency in (str(dep).strip() for dep in (node.get("depends_on") or ())):
            if dependency not in id_set:
                errors.append(f"{node.get('node_id')}: missing dependency {dependency}")
    cycle_result = detect_cycles(nodes)
    if cycle_result["has_cycle"]:
        errors.append(f"cycle detected: {cycle_result['cycles']}")
    try:
        order = topological_sort(nodes) if not errors else ()
    except ValueError as exc:
        errors.append(str(exc))
        order = ()
    if order and len(order) != len(nodes):
        errors.append("topological order did not include all nodes")
    if not nodes:
        warnings.append("DAG has no nodes")
    return {
        "is_valid": not errors,
        "node_count": len(nodes),
        "topological_order": list(order),
        "errors": errors,
        "warnings": warnings,
        "non_claim": NON_CLAIM_TEXT,
    }
