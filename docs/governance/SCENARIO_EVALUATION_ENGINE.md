# Scenario Evaluation Engine v1
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance note |
| Created / authored | Sunday, 2026-05-03 00:00:00 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Timestamp source | Local deterministic decision-chain documentation refactor |
| Status | Active |

## Purpose

Scenario Evaluation Engine v1 upgrades the existing Quant Core scenario surface
from metadata-only diagnostics into deterministic probabilistic scenario
evaluation.

The engine is diagnostic only. It does not emit BUY or SELL recommendations,
live execution instructions, production trading authority, or learned
meta-model authority.

## Invocation

The engine is opt-in from the Quant Core runner:

```bash
python scripts/run_quant_core.py --enable-scenario-engine
```

Optional controls:

- `--scenario-probability-method deterministic_v1`
- `--scenario-calibration-lookback 252`

The runner executes the engine after forecasts, consensus, risk, regime,
strategy metrics, model health, and analysis packets are available.

## Inputs

Scenario v1 uses existing Quant Core artifacts:

- `full_model_predictions.csv`
- `model_consensus_summary.csv`
- `model_health_summary.csv`
- `risk_summary.csv`
- `regime_summary.csv`
- `strategy_metrics.csv`
- `analysis_packets.jsonl`

Missing optional risk, regime, strategy, or health data increases uncertainty
but does not stop artifact generation.

## Scenario Labels

The v1 label set is fixed:

- `bull`
- `bear`
- `sideway`
- `high_volatility`
- `drawdown`
- `recovery`
- `uncertain`

Probabilities are normalized to sum to 1 for each
`ticker x timestamp x horizon x target_type x run_mode x core_run_id` context.

## Probability Method

`deterministic_v1` combines:

- model agreement and sign share
- prediction dispersion
- regime probabilities
- volatility, VaR/CVaR, and drawdown state
- active long/short signal counts from analysis packets
- strategy Sharpe where available
- model health status and run success rates

The method is deterministic and does not run additional training.

## Calibration

Calibration uses realized outcomes already present in Quant Core forecasts when
available. It computes:

- probability bins
- observed frequency
- calibration error
- Brier score
- expected calibration error
- confidence-adjusted probability

When realized outcomes are unavailable, calibration fields remain uncalibrated
instead of being imputed from future data.

## Dominance

Dominance is selected from:

- top confidence-adjusted probability
- gap between the top and second scenario
- uncertainty penalty
- calibration penalty
- downside-risk penalty

Dominance labels:

- `dominant`
- `weak_dominance`
- `no_clear_dominance`
- `uncalibrated_dominance`
- `risk_overrides_dominance`

These labels describe diagnostic confidence only.

## Analysis Packet Enrichment

When enabled, `analysis_packets.jsonl` receives:

- `scenario_summary`
- `dominant_scenario`
- `dominant_scenario_probability`
- `scenario_uncertainty_score`
- `scenario_dominance_score`
- `scenario_calibration_error`
- `scenario_confidence_bucket`
- `alternative_scenarios`

Downstream users should treat these fields as scenario diagnostics, not final
trade instructions.
