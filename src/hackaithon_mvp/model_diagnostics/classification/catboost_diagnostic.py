"""Metadata-only adapter for Catboost."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class CatboostDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'catboost'
    display_name = 'Catboost'
    model_family = 'classification'
    supported_targets = ('absolute_direction',)
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static classifier metadata for local historical direction review.'
    is_exploratory = False
    dependency_status = 'missing_dependency'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
