"""Metadata-only adapter for Cnn Lstm."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class CnnLstmDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'cnn_lstm'
    display_name = 'Cnn Lstm'
    model_family = 'deep_learning'
    supported_targets = ('absolute_direction', 'market_relative_vn30')
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static sequence-model metadata for local historical review.'
    is_exploratory = False
    dependency_status = 'optional_dependency'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
