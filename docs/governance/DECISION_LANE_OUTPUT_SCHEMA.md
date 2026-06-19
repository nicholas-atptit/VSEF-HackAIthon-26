# Decision Lane Output Schema
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance schema |
| Created / authored | Sunday, 2026-05-03 00:00:00 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Timestamp source | Local deterministic decision-chain documentation refactor |
| Status | Active |

## Purpose

Decision Lane v2 is a diagnostic candidate surface for Quant Core outputs. It
does not create BUY or SELL recommendations. It enriches the legacy
`decision_lane_candidates.csv` filter with scenario context, model disagreement,
Risk Governance Layer v1 outputs, and compact reason text for analyst review.

Decision Lane v2 has no live execution, production trading, or learned
meta-model authority.

## Legacy Candidate Artifact

`decision_lane_candidates.csv` remains backward compatible. It is still built
from analysis packets using:

- tradable target rows
- positive primary prediction
- `medium` or `high` agreement bucket
- at least one active policy signal

The legacy field set is unchanged:

- `packet_id`
- `timestamp`
- `ticker`
- `group_name`
- `horizon`
- `target_type`
- `run_mode`
- `primary_model_name`
- `primary_prediction`
- `model_agreement_score`
- `agreement_bucket`
- `regime_label`
- `volatility_bucket`
- `active_signal_count`
- `top_policy_model`
- `top_policy_sharpe`
- `candidate_score`

## Enriched Candidate Artifact

When Risk Governance Layer v1 is enabled, Quant Core writes
`decision_lane_enriched_candidates.csv`.

Required fields:

- `candidate_id`
- `source_packet_id`
- `timestamp`
- `ticker`
- `horizon`
- `target_type`
- `run_mode`
- `core_run_id`
- `primary_model_name`
- `primary_prediction`
- `candidate_score`
- `model_agreement_score`
- `disagreement_score`
- `agreement_bucket`
- `sign_conflict`
- `dominant_scenario`
- `dominant_scenario_probability`
- `scenario_confidence_bucket`
- `scenario_alignment`
- `risk_score`
- `risk_level`
- `risk_action`
- `risk_adjusted_confidence`
- `risk_adjusted_candidate_score`
- `candidate_status`
- `reason_codes`
- `reason_summary`

## Scenario Alignment

`scenario_alignment` is deterministic:

- `aligned`: positive primary prediction with `bull` or `recovery`
- `weakly_aligned`: positive primary prediction with `sideway` or `uncertain`
- `misaligned_or_risky`: positive primary prediction with `bear`, `drawdown`,
  or `high_volatility`
- `unknown`: scenario data is missing or the row does not match the positive
  prediction alignment rules

## Risk Context

`risk_adjusted_confidence` is:

```text
model_agreement_score * confidence_adjustment_factor
```

The confidence adjustment factor comes from Risk Governance Layer v1 when
available. Missing risk context defaults to `1.0`.

`candidate_status` is derived from risk fields:

- `force_hold` when Risk Governance sets `force_hold`
- `blocked` when Risk Governance sets `block_candidate`
- `reduced` when `risk_action` is `reduce_candidate`
- `adjusted` when `risk_action` is `adjust_confidence`
- `diagnostic_candidate` otherwise

## Reason Codes

`reason_codes` is a pipe-separated set of compact diagnostic labels. Supported
labels include:

- `scenario_aligned`
- `scenario_weakly_aligned`
- `scenario_misaligned_or_risky`
- `high_model_agreement`
- `medium_model_agreement`
- `sign_conflict`
- `risk_adjusted`
- `risk_reduced`
- `risk_blocked`
- `force_hold`
- `high_volatility`
- `elevated_drawdown`
- `severe_drawdown`
- `weak_model_health`
- `failing_model_health`

`reason_summary` converts the compact codes into one short human-readable
diagnostic sentence.

## Manifest

`decision_lane_manifest.json` records:

- Decision Lane version
- artifact filenames and paths
- required enriched fields
- input row counts
- output row counts
- scenario alignment rules
- diagnostic-only authority
- no BUY/SELL recommendation authority
