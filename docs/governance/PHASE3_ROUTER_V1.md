# Phase 3 Router v1 Governance
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance note |
| Created / authored | Friday, 2026-05-01 01:36:14 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `dc76edd78a8b3ba8541a5b3691a345c49ceec67c` |
| Timestamp source | Local decision-chain audit fix |
| Status | Active |

## Purpose

Phase 3 Router v1 is a deterministic diagnostic post-processor for Portfolio
Allocator v1 outputs and saved Quant Core context. It converts allocation rows
into governed route decisions that can be audited before any future
recommendation or execution layer is considered.

Phase 3 Router v1 emits route decisions only. It does not emit BUY or SELL
recommendations, does not execute trades, and does not train a learned
meta-model.

## Schema Authority

`docs/governance/PHASE3_ROUTER_OUTPUT_SCHEMA.md` is the source of truth for
canonical router artifact names, required fields, and valid `route_decision`
values. This governance note describes the operating boundary and should not
introduce names that conflict with that schema.

## Inputs

Canonical file-runner context:

- `portfolio_allocation.csv`
- `portfolio_summary.csv`
- `portfolio_risk_summary.csv`

Optional context:

- `allocator_manifest.json`

Missing optional context does not crash the router. Missing allocator outputs
produce a valid diagnostic `no_candidate` route row with missing-output context.

## Outputs

Canonical router outputs:

- `router_decisions.csv`
- `router_summary.csv`
- `router_manifest.json`

Legacy aliases may be written only when explicitly requested by lower-level
writer code with `write_legacy_aliases=True`. They are not canonical outputs and
must not be listed as required artifacts:

- `route_decision.csv`
- `phase3_decision_cards.jsonl`
- `routing_summary.csv`
- `routing_manifest.json`

These outputs are diagnostic routing artifacts. They do not authorize trade
execution.

## Route Decisions

Canonical `route_decision` values:

- `route_allocation_candidate`
- `hold`
- `reject`
- `no_candidate`

Legacy route labels such as `hold_for_review`, `reject_low_confidence`,
`reject_high_risk`, `reject_low_agreement`, `reject_unhealthy_model`,
`reject_allocator_no_allocation`, and `rejected_missing_required_data` are not
valid canonical Phase 3 Router v1 decisions.

## Routing Rules

Default thresholds:

| Setting | Default |
| --- | ---: |
| `risk_reject_threshold` | `0.70` |
| `risk_low_threshold` | `0.35` |
| `risk_elevated_threshold` | `0.55` |
| `confidence_high_threshold` | `0.70` |
| `confidence_medium_threshold` | `0.45` |
| `disagreement_low_threshold` | `0.25` |
| `disagreement_medium_threshold` | `0.50` |
| `dominance_min_threshold` | `0.15` |
| `exposure_near_limit_buffer` | `0.02` |

Rules:

- If `allocation_status != allocation_candidate`, emit `no_candidate`.
- If `risk_level == level_3_hard_override`, `risk_score >= risk_reject_threshold`,
  or severe conflict is present, emit `reject`.
- If final weight is non-positive, emit `hold`.
- If adverse scenario or high-volatility context is present, bias to `hold` and
  emit `reject` only when elevated risk is also present.
- If confidence or disagreement is in the medium band, conflict is mild,
  scenario dominance is weak, or portfolio exposure room is constrained, emit
  `hold`.
- Route surviving low-risk, high-confidence, low-disagreement rows as
  `route_allocation_candidate`.
- Preserve deterministic reproducibility for identical inputs and configuration.

## No-Candidate Behavior

The router treats allocator no-allocation as a valid governed outcome. It writes
a `no_candidate` row rather than forcing an allocation. This preserves the
conservative behavior established by Portfolio Allocator v1.

## Why This Is Not a BUY/SELL Recommendation

The router is a diagnostic governance layer. It does not execute trades, does
not train a learned meta-model, does not select random seeds, and does not
certify production readiness. A routed allocation candidate is still only a
route decision for review.

## Claim Boundaries

| Claim | Allowed? | Reason |
| --- | --- | --- |
| The router emits deterministic route decisions. | Yes | Outputs are generated from saved artifacts and explicit config only. |
| The router can reject or hold weak allocation candidates. | Yes | Risk, confidence, disagreement, conflict, scenario, and exposure gates are explicit. |
| The router creates final BUY or SELL recommendations. | No | Recommendation authority remains out of scope. |
| The router is a learned meta-model. | No | No model is trained in v1. |
| The router grants production trading authority. | No | Live execution, monitoring, validation, and recommendation governance are not implemented. |

## Example CLI Command

```powershell
python scripts/run_phase3_router.py `
  --input-dir tmp\portfolio_allocator_v1_smoke `
  --output-dir tmp\phase3_router_v1_smoke `
  --max-risk-score 0.70
```

The CLI writes only canonical router outputs. Previously advertised flags such
as `--min-allocation-weight`, `--min-candidate-score`,
`--min-model-agreement`, `--low-agreement-action`, and
`--allow-no-allocation` are legacy and are not supported by the current CLI.

Use ignored local output directories such as `tmp/` or `artifacts/` for
generated router artifacts.

## Limitations

- The router is deterministic and rule-based; it is not a trained routing model.
- It depends on Portfolio Allocator v1 and Quant Core artifact quality.
- Missing optional diagnostics reduce routing context.
- It does not prove future profitability.
- It does not replace formal portfolio validation or execution controls.

## Next Step

Run medium or `decision_core` validation after allocator and router real-output
smoke checks. The validation should confirm that allocator outputs and router
outputs remain schema-stable on real Quant Core artifacts before any broader
Phase 3 routing audit is promoted.

## Future Learned Meta-Model Requirements

A learned Phase 3 meta-model should remain out of scope until the project has
enough validated out-of-sample history. Before training a learned router, the
repository should have:

- Walk-forward validation across multiple market regimes.
- Leakage controls that prevent test-period selection.
- Benchmark comparisons against this deterministic router.
- Seed-stability diagnostics for any stochastic route component.
- Clear governance labels that separate candidates from recommendations.
