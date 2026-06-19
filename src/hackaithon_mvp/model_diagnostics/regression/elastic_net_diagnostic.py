"""Metadata-only adapter for Elastic Net Regression."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class ElasticNetDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'elastic_net'
    display_name = 'Elastic Net Regression'
    model_family = 'regression'
    supported_targets = ('forward_return', 'price_return')
    supported_horizons = (5, 10, 20, 40, 60)
    diagnostic_scope = 'Static return and price metadata for local historical review.'
    is_exploratory = True
    dependency_status = 'available'
    source_paths = ('reports/results/VN30_MODEL_UNIVERSE_V6_PRICE_RETURN_ABSOLUTE_CONFIRMATION_RESULT_SUMMARY.md', 'reports/results/VN30_MODEL_UNIVERSE_V1_V6_CLOSEOUT_REPORT.md')
