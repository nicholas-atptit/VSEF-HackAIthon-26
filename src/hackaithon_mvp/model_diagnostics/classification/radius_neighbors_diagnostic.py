"""Metadata-only adapter for Radius Neighbors."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class RadiusNeighborsDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'radius_neighbors'
    display_name = 'Radius Neighbors'
    model_family = 'classification'
    supported_targets = ('absolute_direction',)
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static classifier metadata for local historical direction review.'
    is_exploratory = False
    dependency_status = 'available'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
