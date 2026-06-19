# Pipeline Contracts
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance contract |
| Created / authored | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Timestamp source | Local deterministic decision-chain documentation refactor |
| Status | Active |

## Purpose

This document records the artifact contracts between active deterministic
decision-diagnostic layers:

```text
Quant Core
-> Scenario Evaluation Engine v1
-> Risk Governance Layer v1
-> Decision Lane v2
-> Portfolio Allocator v1
-> Phase 3 Router v1
```

All transitions are diagnostic-only. None of these contracts grants BUY, SELL,
live execution, production trading, or learned meta-model authority.

## Shared Context Keys

The preferred cross-layer context keys are:

- `timestamp`
- `ticker`
- `horizon`
- `target_type`
- `run_mode`
- `core_run_id`

Packet and candidate layers also preserve:

- `packet_id`
- `candidate_id`
- `source_packet_id`
- `allocation_id`

When a key is absent in a source table, the consuming layer falls back only to
documented deterministic defaults or emits missing-input diagnostics.

## Transition Contracts

| Transition | Input artifact | Output artifact | Required fields | Join keys | Downstream consumer | Missing-input behavior |
| --- | --- | --- | --- | --- | --- | --- |
| Quant Core -> Scenario Evaluation Engine v1 | `full_model_predictions.csv`, `model_consensus_summary.csv`, `risk_summary.csv`, `regime_summary.csv`, `strategy_metrics.csv`, `analysis_packets.jsonl`, `model_health_summary.csv` | `scenario_probability.csv`, `scenario_rankings.csv`, `scenario_dominance_summary.csv`, `scenario_uncertainty_summary.csv`, `scenario_calibration_summary.csv`, `scenario_manifest.json` | Forecast context: `timestamp`, `ticker`, `horizon`, `target_type`, `run_mode`, `core_run_id`, `model_name`, `y_pred`; packet context: `packet_id`, `primary_prediction`, `model_agreement_score`; scenario outputs require `scenario_id`, `scenario_label`, `scenario_probability`, `confidence_adjusted_probability`, `dominance_score`, `uncertainty_score`, `calibration_error`. | `timestamp`, `ticker`, `horizon`, `target_type`, `run_mode`, `core_run_id`; packet enrichment also uses `packet_id`. | Risk Governance Layer v1 and Decision Lane v2. | Missing calibration or sparse realized context is recorded as uncalibrated or lower-confidence scenario diagnostics. Missing optional source context does not create trading authority. |
| Scenario Evaluation Engine v1 -> Risk Governance Layer v1 | `scenario_dominance_summary.csv`, `scenario_uncertainty_summary.csv`, `scenario_probability.csv`, plus `decision_lane_candidates.csv` and `analysis_packets.jsonl` from Quant Core | `risk_governance_summary.csv`, `risk_adjusted_candidates.csv`, `risk_override_log.csv`, `risk_manifest.json` | Candidate fields: `packet_id`, `timestamp`, `ticker`, `horizon`, `target_type`, `run_mode`, `primary_prediction`, `candidate_score`, `model_agreement_score`; scenario fields: `dominant_scenario`, `dominance_score`, `scenario_confidence_bucket`, `uncertainty_score`, `calibration_error`, `downside_risk`; risk outputs require `risk_score`, `risk_level`, `risk_action`, `confidence_adjustment_factor`, `block_candidate`, `force_hold`, `risk_reason_codes`. | `packet_id`; `timestamp`, `ticker`, `horizon`, `target_type`, `run_mode`, `core_run_id`. | Decision Lane v2. | If no candidates are present, Risk Governance emits schema-stable empty artifacts. Missing optional scenario context uses conservative defaults and does not block artifact writing. |
| Risk Governance Layer v1 -> Decision Lane v2 | `risk_adjusted_candidates.csv`, `risk_governance_summary.csv`, `decision_lane_candidates.csv`, `analysis_packets.jsonl`, optional scenario artifacts | `decision_lane_enriched_candidates.csv`, `decision_lane_manifest.json` | Required enriched fields include `candidate_id`, `source_packet_id`, `timestamp`, `ticker`, `horizon`, `target_type`, `run_mode`, `core_run_id`, `candidate_score`, `model_agreement_score`, `disagreement_score`, `dominant_scenario`, `scenario_alignment`, `risk_score`, `risk_level`, `risk_action`, `risk_adjusted_confidence`, `risk_adjusted_candidate_score`, `candidate_status`, `reason_codes`, `reason_summary`. | `packet_id` to `source_packet_id`; `timestamp`, `ticker`, `horizon`, `target_type`, `run_mode`, `core_run_id`. | Portfolio Allocator v1. | If Risk Governance did not run, the top-level runner does not write enriched Decision Lane v2 artifacts. Missing scenario context maps to `unknown` alignment. |
| Decision Lane v2 -> Portfolio Allocator v1 | `decision_lane_enriched_candidates.csv`, optional `risk_adjusted_candidates.csv`, optional `scenario_dominance_summary.csv` | `portfolio_allocation.csv`, `portfolio_summary.csv`, `portfolio_risk_summary.csv`, `portfolio_decision_cards.jsonl`, `allocator_manifest.json` | Required allocator input fields are the enriched candidate fields plus risk and scenario context: `candidate_id`, `source_packet_id`, `ticker`, `risk_adjusted_confidence`, `risk_adjusted_candidate_score`, `risk_score`, `risk_level`, `risk_action`, `disagreement_score`, `dominance_score`, `dominant_scenario`, `dominant_scenario_probability`, `scenario_alignment`, `candidate_status`. Outputs require `allocation_id`, `allocation_status`, `final_weight`, exposure fields, and `allocation_reason_codes`. | `candidate_id`, `source_packet_id`; context keys for optional joins. | Phase 3 Router v1. | If enriched candidates are missing, Portfolio Allocator emits all-cash `no_allocation` diagnostics with `missing_enriched_candidates`. Candidates that fail gates become `no_allocation` rows, not trade instructions. |
| Portfolio Allocator v1 -> Phase 3 Router v1 | `portfolio_allocation.csv`, `portfolio_summary.csv`, `portfolio_risk_summary.csv`, optional `allocator_manifest.json` | `router_decisions.csv`, `router_summary.csv`, `router_manifest.json` | Allocation fields: `allocation_id`, `candidate_id`, `source_packet_id`, `timestamp`, `ticker`, `horizon`, `allocation_status`, `final_weight`, `risk_level`, `risk_score`, `risk_adjusted_confidence`, `disagreement_score`, `dominance_score`, `scenario_alignment`, `dominant_scenario`; summary fields: `portfolio_status`, `total_exposure`, `cash_weight`, `min_cash_buffer`, `max_total_exposure`; router outputs require `route_decision`, `route_reason`, `route_reason_codes`, diagnostic authority flags. | `allocation_id`, `candidate_id`, `source_packet_id`; optional risk summary joins by `ticker`. | Human review, audits, and future diagnostic-only downstream layers. | Missing allocator outputs produce a valid `no_candidate` row. Allocator `no_allocation` rows become `no_candidate`. Legacy alias files are optional only and not canonical. |

## Canonical Decision Values

Portfolio Allocator v1 emits:

- `allocation_candidate`
- `no_allocation`

Phase 3 Router v1 emits:

- `route_allocation_candidate`
- `hold`
- `reject`
- `no_candidate`

These values are diagnostics only.
