"""Metadata-only adapter for Validation Weighted Soft Vote."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class ValidationWeightedSoftVoteDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'validation_weighted_soft_vote'
    display_name = 'Validation Weighted Soft Vote'
    model_family = 'ensemble_regime'
    supported_targets = ('absolute_direction', 'regime_context')
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static ensemble and regime metadata for local historical review.'
    is_exploratory = False
    dependency_status = 'not_required_for_static_mvp'
    source_paths = ('reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv', 'reports/generated/vn30_model_universe_benchmark/model_universe_registry.md')
