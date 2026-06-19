"""Metadata-only adapter for Regime Context Xgboost."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class RegimeContextXgboostDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'regime_context_xgboost'
    display_name = 'Regime Context Xgboost'
    model_family = 'ensemble_regime'
    supported_targets = ('absolute_direction', 'regime_context')
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static ensemble and regime metadata for local historical review.'
    is_exploratory = False
    dependency_status = 'optional_dependency'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
