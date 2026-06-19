# Risk Governance Output Schema
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance schema |
| Created / authored | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Timestamp source | Local deterministic decision-chain documentation refactor |
| Status | Active |

## Authority Boundary

Risk Governance Layer v1 is deterministic and diagnostic-only. It emits risk
scores, risk levels, risk actions, candidate confidence adjustments, and risk
reason codes. It does not emit BUY or SELL recommendations, live execution
instructions, production trading authority, or learned meta-model authority.

## Inputs

Required:

- `decision_lane_candidates.csv` or an equivalent DataFrame
- `analysis_packets.jsonl` or an equivalent DataFrame

Optional context:

- `risk_summary.csv`
- `model_consensus_summary.csv`
- `model_health_summary.csv`
- `scenario_dominance_summary.csv`
- `scenario_uncertainty_summary.csv`
- `scenario_probability.csv`

Preferred join keys:

- `packet_id`
- `timestamp`
- `ticker`
- `horizon`
- `target_type`
- `run_mode`
- `core_run_id`

## Outputs

- `risk_governance_summary.csv`
- `risk_adjusted_candidates.csv`
- `risk_override_log.csv`
- `risk_manifest.json`

If no candidates are available, the layer emits schema-stable empty artifacts
and records zero row counts in the manifest.

## Risk Components

`risk_score` is a deterministic weighted score over normalized 0-1 components:

```text
risk_score =
  0.20 * drawdown_component
+ 0.20 * volatility_component
+ 0.15 * downside_risk_component
+ 0.15 * model_health_component
+ 0.15 * scenario_dispersion_component
+ 0.10 * disagreement_component
+ 0.05 * calibration_component
```

All components are bounded to `[0.0, 1.0]`, and the final score is rounded to a
stable six-decimal value.

## Component Sources

| Component | Source logic |
| --- | --- |
| `drawdown_component` | Uses drawdown state when available; otherwise maps current or max drawdown. Severe drawdown maps to `1.00`, elevated drawdown to `0.50`. |
| `volatility_component` | Uses explicit component when present, otherwise normalizes volatility fields against `volatility_reference = 0.08` and considers volatility bucket. |
| `downside_risk_component` | Normalizes VaR, CVaR, expected shortfall, and scenario downside risk against `downside_risk_reference = 0.12`. |
| `model_health_component` | Maps model health status with `healthy = 0.00`, `brittle = 0.35`, `weak = 0.70`, `failing = 1.00`. |
| `scenario_dispersion_component` | Uses scenario uncertainty, entropy, dispersion, weak dominance, or low probability gap. |
| `disagreement_component` | Uses agreement bucket, disagreement score, model disagreement score, inverse agreement, and sign conflict. |
| `calibration_component` | Normalizes calibration error against `calibration_error_reference = 0.25` and considers scenario confidence bucket. |

## Risk Levels

Valid `risk_level` values:

- `level_1_soft_adjustment`
- `level_2_candidate_filtering`
- `level_3_hard_override`

Default thresholds:

- `level_2_min = 0.35`
- `level_3_min = 0.70`

## Risk Actions

Valid `risk_action` values:

- `pass`
- `adjust_confidence`
- `reduce_candidate`
- `block_candidate`
- `force_hold`

Action selection:

- `risk_score >= 0.70`: `level_3_hard_override`, `force_hold = true`,
  `block_candidate = true`.
- `0.35 <= risk_score < 0.70`: `level_2_candidate_filtering`; weak candidates
  use `block_candidate`, otherwise `reduce_candidate`.
- `risk_score < 0.35`: `level_1_soft_adjustment`; scores at or below
  `pass_risk_score_threshold = 0.05` use `pass`, otherwise
  `adjust_confidence`.

## Confidence Adjustment

`confidence_adjustment_factor` is:

```text
max(0.0, 1.0 - risk_score)
```

`risk_adjusted_candidate_score` is:

```text
candidate_score * confidence_adjustment_factor
```

## Candidate Flags

`block_candidate` is a deterministic boolean used by downstream diagnostic
candidate and allocator layers. It means the candidate is blocked from the
diagnostic allocation path.

`force_hold` is a deterministic boolean used to force conservative downstream
diagnostic handling. It is not a trade hold order.

## Reason Codes

`risk_reason_codes` is a pipe-separated string. Current reason labels include:

- `none`
- `severe_drawdown`
- `elevated_drawdown`
- `volatility_spike`
- `high_downside_risk`
- `failing_model_health`
- `weak_model_health`
- `high_scenario_dispersion`
- `low_model_agreement`
- `sign_conflict`
- `poor_calibration`
- `risk_overrides_scenario`

## risk_governance_summary.csv

Required fields:

- `packet_id`
- `timestamp`
- `ticker`
- `horizon`
- `target_type`
- `run_mode`
- `core_run_id`
- `risk_score`
- `risk_level`
- `risk_action`
- `confidence_adjustment_factor`
- `block_candidate`
- `force_hold`
- `risk_reason_codes`
- `drawdown_component`
- `volatility_component`
- `downside_risk_component`
- `model_health_component`
- `scenario_dispersion_component`
- `disagreement_component`
- `calibration_component`

## risk_adjusted_candidates.csv

Contains the original candidate fields plus risk governance fields, including:

- `risk_score`
- `risk_level`
- `risk_action`
- `confidence_adjustment_factor`
- `risk_adjusted_candidate_score`
- `candidate_eligible_after_risk`
- `model_health_status`
- `block_candidate`
- `force_hold`
- `risk_reason_codes`

## risk_override_log.csv

Contains the subset of adjusted candidates where at least one of the following
is true:

- `risk_action` is `reduce_candidate`
- `risk_action` is `block_candidate`
- `risk_action` is `force_hold`
- `block_candidate` is true
- `force_hold` is true

## risk_manifest.json

The manifest records:

- manifest type
- version
- scoring weights
- thresholds
- risk levels
- risk actions
- required fields
- artifact filenames and paths
- input row counts
- output row counts
- diagnostic-only authority
- no BUY/SELL recommendation authority
- deterministic generated timestamp when available
