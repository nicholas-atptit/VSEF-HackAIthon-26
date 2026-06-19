# Portfolio Allocator Output Schema
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

## Authority Boundary

Portfolio Allocator v1 is a deterministic diagnostic allocation layer. It emits
only `allocation_candidate` or `no_allocation` rows and has no BUY or SELL
recommendation authority.

## Inputs

Required:

- `decision_lane_enriched_candidates.csv`

Optional context:

- `risk_adjusted_candidates.csv`
- `scenario_dominance_summary.csv`
- portfolio allocator config

If enabled without enriched Decision Lane v2 candidates, the allocator emits a
valid all-cash diagnostic result with `missing_enriched_candidates`.

## Outputs

- `portfolio_allocation.csv`
- `portfolio_summary.csv`
- `portfolio_risk_summary.csv`
- `portfolio_decision_cards.jsonl`
- `allocator_manifest.json`

## Default Config

These defaults mirror `src.portfolio_allocator.schema.PortfolioAllocatorConfig`
and are the canonical Portfolio Allocator v1 config contract:

| Field | Default |
| --- | ---: |
| `max_position_weight` | `0.20` |
| `min_position_weight` | `0.02` |
| `min_cash_buffer` | `0.30` |
| `max_total_exposure` | `0.70` |
| `confidence_threshold` | `0.45` |
| `disagreement_threshold` | `0.50` |
| `dominance_threshold` | `0.15` |

`effective_max_exposure` is:

```text
min(max_total_exposure, 1 - min_cash_buffer)
```

With defaults, `effective_max_exposure = 0.70`.

## portfolio_allocation.csv

Required fields:

- `allocation_id`
- `candidate_id`
- `source_packet_id`
- `timestamp`
- `ticker`
- `horizon`
- `target_type`
- `run_mode`
- `allocation_status`
- `no_allocation_reason`
- `risk_adjusted_confidence`
- `risk_adjusted_candidate_score`
- `risk_score`
- `risk_level`
- `risk_action`
- `disagreement_score`
- `dominance_score`
- `dominant_scenario`
- `dominant_scenario_probability`
- `scenario_alignment`
- `raw_weight`
- `final_weight`
- `exposure_before_allocation`
- `exposure_after_allocation`
- `cash_buffer_after_allocation`
- `allocation_reason_codes`

Additional diagnostic fields:

- `allocation_priority_score`
- `normalized_risk_adjusted_candidate_score`

Valid `allocation_status` values:

- `allocation_candidate`
- `no_allocation`

## Gating Rules

The allocator emits `no_allocation` when any of these are true:

- `candidate_status` is `blocked` or `force_hold`
- `risk_level` is `level_3_hard_override`
- `risk_action` is `force_hold`
- `risk_adjusted_confidence < confidence_threshold`
- `disagreement_score > disagreement_threshold`
- `dominance_score < dominance_threshold`
- `scenario_alignment` is `misaligned_or_risky`
- `scenario_confidence_bucket` is `low`

## Ranking

Passing candidates are prioritized by:

- lower `disagreement_score`
- higher `dominance_score`
- higher `risk_adjusted_confidence`
- higher `risk_adjusted_candidate_score`
- lower `risk_score`

`allocation_priority_score` is:

```text
0.35 * risk_adjusted_confidence
+ 0.25 * normalized_risk_adjusted_candidate_score
+ 0.20 * dominance_score
+ 0.10 * (1 - disagreement_score)
+ 0.10 * (1 - risk_score)
```

## Sizing

`raw_weight` is:

```text
max_position_weight
* risk_adjusted_confidence
* dominance_multiplier
* agreement_multiplier
* risk_multiplier
* scenario_alignment_multiplier
```

Risk multipliers:

- `level_1_soft_adjustment`: `1.00`
- `level_2_candidate_filtering`: `0.50`
- `level_3_hard_override`: `0.00`

Scenario alignment multipliers:

- `aligned`: `1.00`
- `weakly_aligned`: `0.50`
- `misaligned_or_risky`: `0.00`
- `unknown`: `0.40`

Dominance multipliers:

- `dominance_score >= 0.30`: `1.00`
- `0.15 <= dominance_score < 0.30`: `0.70`
- `dominance_score < 0.15`: `0.00`

Agreement multiplier:

- `1 - disagreement_score`

## Exposure Rules

- Total exposure cannot exceed `max_total_exposure`.
- Cash weight must remain greater than or equal to `min_cash_buffer`.
- `final_weight` cannot exceed `max_position_weight`.
- If remaining exposure room is smaller than `raw_weight`, `final_weight` is reduced.
- If `final_weight < min_position_weight`, the row becomes `no_allocation`.
- If no candidates are allocated, `portfolio_summary.csv` reports `portfolio_status = all_cash`.

## portfolio_summary.csv

Fields:

- `portfolio_status`
- `candidate_count`
- `allocation_candidate_count`
- `no_allocation_count`
- `total_exposure`
- `cash_weight`
- `min_cash_buffer`
- `max_total_exposure`
- `effective_max_exposure`
- `diagnostic_only_authority`
- `no_buy_sell_recommendation_authority`
- `no_forced_trade_rule`

## portfolio_risk_summary.csv

Fields:

- `portfolio_status`
- `allocation_candidate_count`
- `total_exposure`
- `cash_weight`
- `max_position_weight`
- `max_single_position_weight`
- `weighted_average_risk_score`
- `max_allocated_risk_score`
- `level_1_soft_adjustment_count`
- `level_2_candidate_filtering_count`
- `level_3_hard_override_count`
- `no_allocation_count`

## portfolio_decision_cards.jsonl

Each line is a compact JSON card with:

- `allocation_id`
- `ticker`
- `allocation_status`
- `final_weight`
- `dominant_scenario`
- `risk_level`
- `risk_adjusted_confidence`
- `no_allocation_reason`
- `allocation_reason_codes`
- `diagnostic_only_authority`
- `no_buy_sell_recommendation_authority`

## allocator_manifest.json

The manifest records:

- version
- config
- thresholds
- input row counts
- output row counts
- artifact filenames and paths
- required allocation fields
- diagnostic-only authority
- no BUY/SELL recommendation authority
- no forced trade rule
- missing enriched candidate status
