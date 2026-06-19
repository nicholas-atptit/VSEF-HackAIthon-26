"""Metadata-only adapter for Price Momentum Rule."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class PriceMomentumRuleDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'price_momentum_rule'
    display_name = 'Price Momentum Rule'
    model_family = 'baseline'
    supported_targets = ('absolute_direction',)
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static baseline metadata for local historical comparison review.'
    is_exploratory = False
    dependency_status = 'not_required_for_static_mvp'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
