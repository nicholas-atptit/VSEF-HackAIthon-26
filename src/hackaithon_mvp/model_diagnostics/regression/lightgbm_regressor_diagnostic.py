"""Metadata-only adapter for LightGBM Regressor."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class LightgbmRegressorDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'lightgbm_regressor'
    display_name = 'LightGBM Regressor'
    model_family = 'regression'
    supported_targets = ('forward_return', 'price_return')
    supported_horizons = (5, 10, 20, 40, 60)
    diagnostic_scope = 'Static return and price metadata for local historical review.'
    is_exploratory = True
    dependency_status = 'optional_dependency'
    source_paths = ('configs/experiments/EXP-FA-007.yaml', 'scripts/run_vn100_hybrid_frequency_accuracy_benchmark.py')
