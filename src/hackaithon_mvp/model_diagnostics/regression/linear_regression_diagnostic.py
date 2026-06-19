"""Metadata-only adapter for Linear Regression."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class LinearRegressionDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'linear_regression'
    display_name = 'Linear Regression'
    model_family = 'regression'
    supported_targets = ('forward_return', 'price_return')
    supported_horizons = (5, 10, 20, 40, 60)
    diagnostic_scope = 'Static return and price metadata for local historical review.'
    is_exploratory = True
    dependency_status = 'available'
    source_paths = ('reports/results/VN30_MODEL_UNIVERSE_V1_V6_CLOSEOUT_REPORT.md', 'docs/governance/VSEF_LINEAR_FOLD_DIAGNOSTICS.md')
