"""Metadata-only adapter for Ridge Regression."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class RidgeRegressionDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'ridge_regression'
    display_name = 'Ridge Regression'
    model_family = 'regression'
    supported_targets = ('forward_return', 'price_return')
    supported_horizons = (5, 10, 20, 40, 60)
    diagnostic_scope = 'Static return and price metadata for local historical review.'
    is_exploratory = True
    dependency_status = 'available'
    source_paths = ('reports/results/VN30_MODEL_UNIVERSE_V6_PRICE_RETURN_ABSOLUTE_CONFIRMATION_RESULT_SUMMARY.md', 'reports/generated/vn_forecast_engine_v1/return_price_evaluation.csv')
