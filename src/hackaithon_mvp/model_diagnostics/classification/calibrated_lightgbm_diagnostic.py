"""Metadata-only adapter for Calibrated Lightgbm."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class CalibratedLightgbmDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'calibrated_lightgbm'
    display_name = 'Calibrated Lightgbm'
    model_family = 'classification'
    supported_targets = ('absolute_direction',)
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static classifier metadata for local historical direction review.'
    is_exploratory = False
    dependency_status = 'optional_dependency'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
