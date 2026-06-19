# Quant Core Output Schema
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance note |
| Created / authored | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `5ceed8162b4658cd1ee3402fb147aa5246c1f540` |
| Timestamp source | Local deterministic decision-chain documentation refactor |
| Status | Active |

## Authority Boundary

Quant Core and all optional downstream layers are diagnostic-only. They may emit
forecast diagnostics, scenario diagnostics, risk diagnostics, diagnostic
candidates, allocation candidates, no-allocation states, and route decisions.
They do not emit BUY or SELL recommendations, live execution instructions,
production trading authority, or learned meta-model authority.

## Canonical Artifact Inventory

`scripts/run_quant_core.py` writes artifacts under the requested output
directory. The active implemented chain is:

```text
Quant Core
-> Scenario Evaluation Engine v1
-> Risk Governance Layer v1
-> Decision Lane v2
-> Portfolio Allocator v1
-> Phase 3 Router v1
```

### Base Quant Core

Base Quant Core writes:

- `run_manifest.json`
- `summary.md`
- `scenario_matrix.csv`
- `model_governance.csv`
- `full_model_predictions.csv`
- `forecast_summary.csv`
- `forecast_summary_by_horizon.csv`
- `window_summary.csv`
- `risk_summary.csv`
- `regime_summary.csv`
- `signals.csv`
- `positions.csv`
- `trades.csv`
- `strategy_metrics.csv`
- `equity_curve.csv`
- `policy_summary.csv`
- `model_execution_log.csv`
- `model_consensus_summary.csv`
- `model_health_summary.csv`
- `analysis_packets.jsonl`
- `decision_lane_candidates.csv`

### Scenario Evaluation Engine v1

When `--enable-scenario-engine` is set, the runner also writes:

- `scenario_probability.csv`
- `scenario_rankings.csv`
- `scenario_dominance_summary.csv`
- `scenario_uncertainty_summary.csv`
- `scenario_calibration_summary.csv`
- `scenario_manifest.json`

### Risk Governance Layer v1

When `--enable-risk-governance` is set, the runner also writes:

- `risk_governance_summary.csv`
- `risk_adjusted_candidates.csv`
- `risk_override_log.csv`
- `risk_manifest.json`

### Decision Lane v2

When Risk Governance Layer v1 is enabled, the runner builds Decision Lane v2
enriched outputs:

- `decision_lane_enriched_candidates.csv`
- `decision_lane_manifest.json`

### Portfolio Allocator v1

When `--enable-portfolio-allocator` is set, the runner also writes:

- `portfolio_allocation.csv`
- `portfolio_summary.csv`
- `portfolio_risk_summary.csv`
- `portfolio_decision_cards.jsonl`
- `allocator_manifest.json`

### Phase 3 Router v1

When `--enable-phase3-router` is set, the runner also writes:

- `router_decisions.csv`
- `router_summary.csv`
- `router_manifest.json`

The current smoke-run artifact check is documented in
`docs/audits/VSEF_QUANT_CORE_SMOKE_AUDIT.md`.

## Manifest

`run_manifest.json` records:

- git metadata
- runtime and dependency metadata
- requested and evaluated models
- skipped models with reasons
- run mode and run-mode specification
- requested role filters
- scenario matrix configuration
- artifact paths
- row counts for major output tables

Important additions for governance:

- `run_mode`
- `run_mode_spec`
- `requested_model_roles`
- `governance_output`

When Scenario Evaluation Engine v1 is enabled, `artifact_paths` also records
the scenario artifacts and `run_counts` records scenario probability, ranking,
and dominance row counts.

When Risk Governance Layer v1 is enabled, `artifact_paths` also records the risk
governance artifacts. `run_counts` records risk governance rows, risk-adjusted
candidate rows, and risk override rows.

When Decision Lane v2 enriched outputs are written, `artifact_paths` records
`decision_lane_enriched_candidates` and `decision_lane_manifest`, and
`run_counts` records enriched Decision Lane candidate rows.

When Portfolio Allocator v1 is enabled, `artifact_paths` records the portfolio
allocation artifacts and `run_counts` records portfolio allocation rows and
portfolio decision card rows.

When Phase 3 Router v1 is enabled, `artifact_paths` records the router artifacts
and `run_counts` records router decision and summary rows.

## Full Model Predictions

`full_model_predictions.csv` extends the shared forecast contract with quant-core
governance and scenario metadata.

Base forecast contract:

- `timestamp`
- `ticker`
- `y_true`
- `y_pred`
- `model_name`
- `target_type`
- `horizon`
- `window_id`
- optional `target_timestamp`

Added governance and scenario fields:

- `model_family`
- `model_role`
- `model_status`
- `research_priority`
- `supports_policy_eval`
- `model_notes`
- `core_run_id`
- `preset`
- `group_name`
- `target_name`
- `target_column`
- `target_family`
- `target_tradable`
- `ticker_group_members`
- `run_mode`

## Consensus Summary

`model_consensus_summary.csv` is one row per
`timestamp x ticker x horizon x target_type x run_mode x scenario`.

Core fields:

- `model_count`
- `primary_model_count`
- `comparator_model_count`
- `baseline_model_count`
- `shadow_model_count`
- `ensemble_model_count`
- `agreement_score`
- `disagreement_score`
- `agreement_bucket`
- `sign_conflict`
- `dispersion_score`
- `prediction_range`
- `rank_spread`
- `primary_mean_prediction`
- `comparator_mean_prediction`
- `baseline_mean_prediction`
- `ensemble_prediction`
- `primary_vs_comparator_gap`
- `primary_vs_baseline_gap`
- `ensemble_vs_primary_gap`
- `policy_gate_disagreement_share`
- `active_signal_share`

Notes:

- `agreement_score` is sign-based agreement within the packet.
- `policy_gate_disagreement_share` measures how often policy gating disagrees
  with the raw forecast sign after thresholding and conditioning.
- `agreement_bucket` is a retrieval-friendly summary:
  `high`, `medium`, `low`, `unknown`.

## Analysis Packets

`analysis_packets.jsonl` contains one JSON object per
`ticker x timestamp x horizon x target_type x run_mode x scenario`.

Each packet includes:

- packet identity:
  `packet_id`, `packet_generated_at`
- core dimensions:
  `timestamp`, `ticker`, `horizon`, `target_type`, `target_name`, `run_mode`,
  `core_run_id`, `group_name`
- primary prediction context:
  `primary_model_name`, `primary_model_role`, `primary_prediction`,
  `primary_prediction_summary`
- model-level detail:
  `model_by_model_predictions`, `model_ranks`
- agreement and disagreement:
  `model_agreement_score`, `model_disagreement_score`, `dispersion_score`,
  `sign_conflict`, `rank_spread`, `agreement_bucket`
- cross-role deltas:
  `primary_vs_comparator_gap`, `primary_vs_baseline_gap`,
  `ensemble_vs_primary_gap`
- conditioned execution context:
  `policy_gate_disagreement_share`, `active_signal_count`,
  `long_signal_count`, `short_signal_count`, `mean_position_size`
- policy performance context:
  `top_policy_model`, `top_policy_sharpe`, `top_policy_cagr`
- risk context:
  `risk_summary`, `vol_forecast`, `volatility_bucket`
- regime context:
  `regime_summary`, `regime_label`
- realized outcome context:
  `realized_y_true`, `realized_available`, `target_timestamp`
- retrieval metadata:
  `signal_strength_bucket`, `model_role_context`, `retrieval_metadata`

When Scenario Evaluation Engine v1 is enabled, packets also include:

- `scenario_summary`
- `dominant_scenario`
- `dominant_scenario_probability`
- `scenario_uncertainty_score`
- `scenario_dominance_score`
- `scenario_calibration_error`
- `scenario_confidence_bucket`
- `alternative_scenarios`

JSON-encoded nested fields:

- `primary_prediction_summary`
- `model_by_model_predictions`
- `model_ranks`
- `ensemble_summary`
- `regime_summary`
- `risk_summary`
- `policy_summary`
- `retrieval_metadata`
- `scenario_summary`
- `alternative_scenarios`

## Scenario Evaluation Engine Artifacts

The scenario engine is opt-in via `--enable-scenario-engine`. It is a
deterministic diagnostic layer and does not emit final BUY or SELL authority.

Scenario labels:

- `bull`
- `bear`
- `sideway`
- `high_volatility`
- `drawdown`
- `recovery`
- `uncertain`

`scenario_probability.csv` contains one row per scenario label per
`ticker x timestamp x horizon x target_type x run_mode x core_run_id` context.
`scenario_probability` sums to 1 within each context.

Required Scenario v1 fields:

- `scenario_id`
- `timestamp`
- `ticker`
- `horizon`
- `target_type`
- `run_mode`
- `core_run_id`
- `scenario_label`
- `scenario_probability`
- `confidence_adjusted_probability`
- `expected_outcome`
- `downside_risk`
- `confidence_interval_low`
- `confidence_interval_high`
- `uncertainty_score`
- `dispersion_score`
- `dominance_score`
- `dominant_scenario_flag`
- `calibration_error`
- `historical_hit_rate`
- `source_model`

Additional scenario artifacts:

- `scenario_rankings.csv`: scenario rows with rank and dominance label
- `scenario_dominance_summary.csv`: one dominant-scenario diagnostic row per
  context
- `scenario_uncertainty_summary.csv`: entropy, dispersion, calibration, and
  confidence-bucket diagnostics
- `scenario_calibration_summary.csv`: probability-bin observed frequency,
  calibration error, Brier score, and expected calibration error
- `scenario_manifest.json`: method, labels, source counts, row counts, and
  artifact paths

## Risk Governance Layer Artifacts

Risk Governance Layer v1 is opt-in via `--enable-risk-governance`. It is a
deterministic diagnostic layer that turns Decision Lane candidates and Quant
Core context into risk-adjusted candidate diagnostics.

Risk Governance outputs:

- `risk_governance_summary.csv`: one risk summary row per diagnostic candidate.
- `risk_adjusted_candidates.csv`: candidate rows enriched with risk action,
  confidence adjustment, eligibility, and risk reason fields.
- `risk_override_log.csv`: subset of adjusted candidates with reducing,
  blocking, or force-hold risk actions.
- `risk_manifest.json`: scoring weights, thresholds, artifact paths, row counts,
  required fields, and diagnostic-only authority flags.

See `docs/governance/RISK_GOVERNANCE_OUTPUT_SCHEMA.md` for risk-score formula,
risk levels, risk actions, candidate flags, and required fields.

## Model Health Summary

`model_health_summary.csv` is one row per model aggregated across the full run.

Core fields:

- execution health:
  `run_success_count`, `run_failure_count`, `run_success_rate`,
  `warning_count_total`, `missing_output_count_total`, `failure_reasons`
- forecast quality:
  `forecast_observations_total`, `mean_rmse`, `median_rmse`,
  `rmse_dispersion`, `mean_directional_accuracy`,
  `median_directional_accuracy`, `directional_accuracy_dispersion`
- slice stability:
  `positive_slice_frequency`, `strong_slice_frequency`,
  `window_count`, `window_rmse_dispersion`,
  `window_directional_accuracy_dispersion`
- drift-style summaries:
  `directional_accuracy_drift`, `rmse_drift`, `drift_flag`
- policy summaries:
  `policy_eval_count`, `mean_sharpe`, `median_sharpe`,
  `positive_policy_frequency`, `mean_cagr`, `mean_max_drawdown`
- final label:
  `health_status`

Current `health_status` categories:

- `healthy`
- `brittle`
- `weak`
- `failing`

## Decision Lane Candidates

`decision_lane_candidates.csv` is intentionally conservative. It surfaces packet
rows that are:

- tradable
- positively predicted by the primary model
- in `medium` or `high` agreement buckets
- supported by at least one active policy signal

Key fields:

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

## Decision Lane Enriched Candidates

`decision_lane_enriched_candidates.csv` is emitted when
`--enable-risk-governance` is set. It preserves the legacy candidate artifact and
adds a diagnostic-only enriched surface that joins:

- legacy Decision Lane candidates
- analysis packet model disagreement and scenario fields
- Scenario Evaluation Engine dominance and probability context when available
- Risk Governance Layer v1 risk scores and candidate actions

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

`decision_lane_manifest.json` records the Decision Lane version, required
fields, artifact paths, input and output row counts, scenario alignment rules,
diagnostic-only authority, and no BUY/SELL recommendation authority.

## Portfolio Allocator Artifacts

Portfolio Allocator v1 is opt-in via `--enable-portfolio-allocator`. The flow is:

```text
Quant Core
-> Scenario Evaluation Engine v1 if enabled
-> Risk Governance Layer v1 if enabled
-> Decision Lane v2 enriched candidates
-> Portfolio Allocator v1 if enabled
```

The allocator requires Decision Lane v2 enriched candidates. If the flag is used
without enriched candidates, it emits a valid all-cash diagnostic output with
`missing_enriched_candidates`.

Portfolio outputs:

- `portfolio_allocation.csv`: one diagnostic row per enriched candidate or a
  missing-enriched no-allocation row.
- `portfolio_summary.csv`: portfolio status, total exposure, cash weight, and
  authority flags.
- `portfolio_risk_summary.csv`: exposure and risk-level diagnostics.
- `portfolio_decision_cards.jsonl`: compact candidate cards with diagnostic-only
  authority flags.
- `allocator_manifest.json`: config, thresholds, row counts, artifact paths,
  no forced trade rule, and no BUY/SELL recommendation authority.

Required `portfolio_allocation.csv` fields:

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

Valid allocation statuses:

- `allocation_candidate`
- `no_allocation`

See `docs/governance/PORTFOLIO_ALLOCATOR_OUTPUT_SCHEMA.md` for full gating,
ranking, sizing, exposure, and manifest details.

## Phase 3 Router Artifacts

Phase 3 Router v1 is opt-in via `--enable-phase3-router`. It is a deterministic
diagnostic layer that converts Portfolio Allocator v1 rows into route decisions:

```text
Portfolio Allocator allocation_candidate/no_allocation
-> Phase 3 Router route_allocation_candidate/hold/reject/no_candidate
```

Router outputs:

- `router_decisions.csv`: one diagnostic route row per allocator row, or one
  `no_candidate` row when allocator outputs are unavailable.
- `router_summary.csv`: route counts, routed final weight, exposure context, and
  authority flags.
- `router_manifest.json`: config, thresholds, route counts, required fields,
  artifact paths, and no BUY/SELL recommendation authority.

Required `router_decisions.csv` fields:

- `router_decision_id`
- `allocation_id`
- `candidate_id`
- `source_packet_id`
- `timestamp`
- `ticker`
- `horizon`
- `route_decision`
- `route_reason`
- `allocation_status`
- `final_weight`
- `risk_level`
- `risk_score`
- `risk_adjusted_confidence`
- `disagreement_score`
- `dominance_score`
- `scenario_alignment`
- `dominant_scenario`
- `portfolio_status`
- `total_exposure`
- `cash_weight`
- `route_reason_codes`
- `diagnostic_only_authority`
- `no_buy_sell_recommendation_authority`

Valid route decisions:

- `route_allocation_candidate`
- `hold`
- `reject`
- `no_candidate`

See `docs/governance/PHASE3_ROUTER_OUTPUT_SCHEMA.md` for full routing rules and
manifest details.

## Fallback Provenance

Fallback behavior is explicit in outputs and should remain so for downstream
retrieval and analyst interpretation:

- risk fallback: `var_cvar_drawdown_fallback`
- regime fallback: `markov_switching_threshold_fallback`

These labels make it possible for future RAG, LLM, and human analyst layers to
distinguish full statistical context from degraded but reproducible fallback
context.
