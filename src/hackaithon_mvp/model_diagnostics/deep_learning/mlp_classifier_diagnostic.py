"""Metadata-only adapter for Mlp Classifier."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class MlpClassifierDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'mlp_classifier'
    display_name = 'Mlp Classifier'
    model_family = 'deep_learning'
    supported_targets = ('absolute_direction', 'market_relative_vn30')
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static sequence-model metadata for local historical review.'
    is_exploratory = False
    dependency_status = 'available'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
