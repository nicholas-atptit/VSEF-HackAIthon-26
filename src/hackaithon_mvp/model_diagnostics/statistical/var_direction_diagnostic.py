"""Metadata-only adapter for Var Direction."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class VarDirectionDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'var_direction'
    display_name = 'Var Direction'
    model_family = 'statistical'
    supported_targets = ('absolute_direction', 'volatility_review')
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static time-series metadata for local historical review.'
    is_exploratory = False
    dependency_status = 'optional_dependency'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
