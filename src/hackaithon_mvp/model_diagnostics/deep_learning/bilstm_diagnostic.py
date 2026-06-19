"""Metadata-only adapter for BiLSTM."""

from __future__ import annotations

from ..base import BaseDiagnosticAdapter


class BilstmDiagnosticAdapter(BaseDiagnosticAdapter):
    model_key = 'bilstm'
    display_name = 'BiLSTM'
    model_family = 'deep_learning'
    supported_targets = ('absolute_direction', 'market_relative_vn30')
    supported_horizons = (20, 40, 60, 80)
    diagnostic_scope = 'Static sequence-model metadata for local historical review.'
    is_exploratory = True
    dependency_status = 'optional_dependency'
    source_paths = ('reports/results/VN30_MODEL_UNIVERSE_V4_BILSTM_RELOCK_RESULT_SUMMARY.md', 'reports/claims/VN30_MODEL_UNIVERSE_V4_BILSTM_RELOCK_CLAIM_BOUNDARY.md', 'configs/experiments/EXP-FC-001.yaml')
