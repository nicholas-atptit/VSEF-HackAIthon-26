"""Metadata-only adapter for Random Forest Regressor."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class RandomForestRegressorDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'random_forest_regressor'
    display_name = 'Random Forest Regressor'
    model_family = 'regression'
    supported_targets = ('forward_return', 'price_return')
    supported_horizons = (5, 10, 20, 40, 60)
    diagnostic_scope = 'Static return and price metadata for local historical review.'
    is_exploratory = True
    dependency_status = 'available'
    source_paths = ('src/ml/training/baseline_model.py', 'reports/generated/vn30_model_universe_direction_price/ticker_stability.csv')
