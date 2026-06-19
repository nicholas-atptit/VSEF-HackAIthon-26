# Portfolio Allocator v1 Governance
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance note |
| Created / authored | Thursday, 2026-04-30 20:37:39 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `0c96f76aef54968f0978a4f13003b397a95715da` |
| Timestamp source | Local deterministic decision-chain documentation refactor |
| Status | Active |

## Purpose

Portfolio Allocator v1 is a deterministic diagnostic layer in the active
decision chain:

```text
Quant Core
-> Scenario Evaluation Engine v1
-> Risk Governance Layer v1
-> Decision Lane v2
-> Portfolio Allocator v1
-> Phase 3 Router v1
```

It converts eligible Decision Lane v2 enriched candidates into bounded
diagnostic allocation candidates, or emits a valid `no_allocation` state when
inputs are missing or candidates fail gates.

Portfolio Allocator v1 does not emit BUY or SELL recommendations, live
execution instructions, production trading authority, or learned model
authority.

## Schema Authority

`docs/governance/PORTFOLIO_ALLOCATOR_OUTPUT_SCHEMA.md` is the source of truth
for allocator artifact names, default thresholds, required fields, gating,
ranking, sizing, and exposure rules.

## Inputs

Canonical inputs:

- `decision_lane_enriched_candidates.csv`

Optional context:

- `risk_adjusted_candidates.csv`
- `scenario_dominance_summary.csv`

If enriched Decision Lane v2 candidates are missing, the allocator emits a
valid all-cash diagnostic result with `missing_enriched_candidates`.

## Outputs

Canonical outputs:

- `portfolio_allocation.csv`
- `portfolio_summary.csv`
- `portfolio_risk_summary.csv`
- `portfolio_decision_cards.jsonl`
- `allocator_manifest.json`

The only valid `allocation_status` values are:

- `allocation_candidate`
- `no_allocation`

## Default Config

| Setting | Default |
| --- | ---: |
| `max_position_weight` | `0.20` |
| `min_position_weight` | `0.02` |
| `min_cash_buffer` | `0.30` |
| `max_total_exposure` | `0.70` |
| `confidence_threshold` | `0.45` |
| `disagreement_threshold` | `0.50` |
| `dominance_threshold` | `0.15` |

`effective_max_exposure` is `min(max_total_exposure, 1 - min_cash_buffer)`.

## Gating Rules

The allocator emits `no_allocation` when any candidate has:

- `candidate_status` equal to `blocked` or `force_hold`
- `risk_level` equal to `level_3_hard_override`
- `risk_action` equal to `force_hold`
- `risk_adjusted_confidence < confidence_threshold`
- `disagreement_score > disagreement_threshold`
- `dominance_score < dominance_threshold`
- `scenario_alignment` equal to `misaligned_or_risky`
- `scenario_confidence_bucket` equal to `low`

If all candidates are filtered or sized below `min_position_weight`, the
portfolio state remains all cash and is still a valid diagnostic result.

## Ranking And Sizing

Passing candidates are ranked by deterministic priority fields:

- lower disagreement
- higher dominance
- higher risk-adjusted confidence
- higher risk-adjusted candidate score
- lower risk score

Sizing uses bounded `raw_weight` and `final_weight` rules from
`PORTFOLIO_ALLOCATOR_OUTPUT_SCHEMA.md`. Exposure cannot exceed
`max_total_exposure`, and cash weight must remain greater than or equal to
`min_cash_buffer`.

## Downstream Consumer

Phase 3 Router v1 consumes:

- `portfolio_allocation.csv`
- `portfolio_summary.csv`
- `portfolio_risk_summary.csv`
- optional allocator manifest context

Allocator rows are diagnostic inputs to route decisions. They are not orders or
final portfolio actions.

## Claim Boundaries

| Claim | Allowed? | Reason |
| --- | --- | --- |
| The allocator emits deterministic allocation candidates. | Yes | Outputs are generated from explicit candidate, risk, scenario, and config context. |
| The allocator supports a governed no-allocation state. | Yes | Missing inputs or failed gates produce a valid all-cash diagnostic output. |
| The allocator emits BUY or SELL recommendations. | No | The layer emits only diagnostic `allocation_candidate` or `no_allocation` states. |
| The allocator executes trades. | No | Live execution is not implemented in this chain. |
| The allocator grants production trading authority. | No | Production trading authority is out of scope. |

## Limitations

- The allocator is deterministic and rule-based.
- It depends on Decision Lane v2, Risk Governance, and Scenario artifact quality.
- Missing optional context reduces diagnostic precision.
- It does not validate future profitability.
- It does not replace Phase 3 Router v1; it feeds it.
