"""Metadata-only adapter for Garch Volatility Diagnostic."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class GarchVolatilityDiagnosticDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'garch_volatility_diagnostic'
    display_name = 'Garch Volatility Diagnostic'
    model_family = 'statistical'
    supported_targets = ('absolute_direction', 'volatility_review')
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static time-series metadata for local historical review.'
    is_exploratory = True
    dependency_status = 'optional_dependency'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
