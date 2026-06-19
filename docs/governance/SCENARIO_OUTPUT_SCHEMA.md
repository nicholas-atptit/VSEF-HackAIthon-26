# Scenario Output Schema
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

Scenario Evaluation Engine v1 emits deterministic scenario diagnostics only. It
does not emit BUY or SELL recommendations, live execution instructions,
production trading authority, or learned meta-model authority.

## Artifact Set

When `--enable-scenario-engine` is set, Quant Core writes:

- `scenario_probability.csv`
- `scenario_rankings.csv`
- `scenario_dominance_summary.csv`
- `scenario_uncertainty_summary.csv`
- `scenario_calibration_summary.csv`
- `scenario_manifest.json`

## Required Probability Fields

`scenario_probability.csv` and `scenario_rankings.csv` include the required
Scenario v1 fields:

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

Additional diagnostic fields may be present for auditability, including
realized outcome availability, probability bin, Brier score, regime
probabilities, model agreement, model health factor, volatility, and drawdown
pressure.

## scenario_probability.csv

One row per scenario label per run context.

The normalized context is:

`ticker x timestamp x horizon x target_type x run_mode x core_run_id`

`scenario_probability` sums to 1 within that context.

## scenario_rankings.csv

Extends scenario probability rows with:

- `scenario_rank`
- `dominance_label`
- `probability_gap`

Rank 1 is selected by `confidence_adjusted_probability`.

## scenario_dominance_summary.csv

One row per run context.

Core fields:

- `dominant_scenario`
- `dominant_scenario_probability`
- `dominant_scenario_adjusted_probability`
- `second_scenario`
- `second_scenario_adjusted_probability`
- `probability_gap`
- `dominance_score`
- `dominance_label`
- `dominant_scenario_flag`
- `uncertainty_score`
- `calibration_error`
- `downside_risk`
- `scenario_confidence_bucket`

`dominant_scenario_flag` is false when no clear dominance is detected.

## scenario_uncertainty_summary.csv

One row per run context.

Core fields:

- `scenario_count`
- `probability_entropy`
- `top_probability`
- `second_probability`
- `probability_gap`
- `uncertainty_score`
- `dispersion_score`
- `mean_calibration_error`
- `missing_calibration_share`
- `confidence_bucket`

## scenario_calibration_summary.csv

One row per scenario label and probability bin where realized outcomes are
available.

Core fields:

- `scenario_label`
- `probability_bin`
- `bin_low`
- `bin_high`
- `prediction_count`
- `observed_count`
- `observed_frequency`
- `mean_probability`
- `calibration_error`
- `brier_score`
- `expected_calibration_error`

## scenario_manifest.json

Records:

- Scenario engine version
- probability method
- calibration lookback and bin count
- scenario labels
- diagnostic-only dominance authority
- artifact paths
- source row counts
- output row counts
- probability sums by context
