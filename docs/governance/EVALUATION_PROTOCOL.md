# VSEF v1 Evaluation Protocol

## Document Metadata

| Field | Value |
| --- | --- |
| Document name | VSEF v1 Evaluation Protocol |
| Phase | 0 |
| Status | Frozen for v1 |
| Last updated date | 2026-05-09 |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Owner | Project team / maintainer |
| Document type | Governance protocol |

## Evaluation Principle

VSEF v1 must use time-series-safe evaluation. Random train-test split is not
acceptable for time-series forecasting claims. Walk-forward evaluation is the
preferred validation method where available. Evaluation must avoid leakage from
future data.

This document defines accepted evaluation governance. It does not add new
metrics, change model code, or create new evaluation runtime behavior.

## Supported Evaluation Methods

| Method | v1 status | Purpose | Restrictions |
| --- | --- | --- | --- |
| Fixed chronological train/test split | Supported | Basic time-ordered evaluation with training data before test data | Split date and date window must be preserved in evidence. |
| TimeSeriesSplit-style validation | Supported | Repeated time-ordered validation folds | Fold construction must not expose future observations to earlier folds. |
| Walk-forward evaluation | Preferred where available | Rolling or expanding evaluation that simulates sequential forecasting | Window configuration, horizon, and evaluated dates must be recorded. |
| Model comparison across the same ticker/date/horizon context | Supported | Fair comparison across supported models | Comparisons must use the same ticker, date window, horizon, target, and configuration context. |

Randomized row-level splitting is not accepted for VSEF v1 forecasting claims.

## Standard Metrics

VSEF v1 evaluation evidence may use the following metrics:

| Metric | v1 status | Definition / use | Claim rule |
| --- | --- | --- | --- |
| MAE | Supported | Mean absolute error for forecast magnitude error | May be claimed only when artifact evidence contains the value and context. |
| RMSE | Supported | Root mean squared error for larger-error-sensitive forecast quality | May be claimed only when artifact evidence contains the value and context. |
| MAPE | Documented target / check implementation before claiming | Percentage error where denominator is numerically safe | Do not claim unless implementation and zero/near-zero handling are verified. |
| Directional accuracy | Supported where implemented | Share of observations where predicted direction matches realized direction | May be claimed only with artifact evidence and target definition. |
| Strategy metrics | Supported where strategy diagnostics are generated | Diagnostic strategy summary such as returns, drawdown, Sharpe-like fields, or equivalent existing outputs | Do not invent missing strategy metrics; use only generated `strategy_metrics.csv` evidence. |
| Risk metrics | Supported where risk summaries are generated | Diagnostic risk summary fields from existing risk outputs | Use only generated `risk_summary.csv` or governed risk artifacts. |

If a metric is not currently implemented in the relevant runtime path, it must
be marked as "documented target / check implementation before claiming" and may
not be used as evidence of model quality.

## Required Output Artifacts

Expected evaluation and diagnostic evidence includes:

- `forecast_summary.csv`
- `model_consensus_summary.csv`
- `model_health_summary.csv`
- `risk_summary.csv`
- `strategy_metrics.csv`
- `analysis_packets.jsonl`
- `decision_lane_candidates.csv`
- `run_config.json`
- model manifests

Some existing runtime paths may use `run_manifest.json` or another manifest
name. The evidence requirement is the same: configuration, model list, data
context, and artifact paths must be reviewable.

## Evaluation Evidence Rules

Each evaluation run should preserve:

- Dataset/ticker/horizon context
- Model list
- Date window
- Metrics
- Config
- Manifest or run metadata

No evaluation claim should be made without artifact evidence. A defensible claim
must identify the ticker or dataset, forecast horizon, target, model list,
training and evaluation date window, metric definition, configuration, and
artifact path.

## Walk-forward Role

Walk-forward evaluation is the preferred VSEF v1 validation method because it
preserves chronological order and tests models in the sequence in which
forecasts would have been made. It reduces the risk of data leakage compared
with random train-test splits and gives reviewers a clearer view of model
behavior across time.

Walk-forward output is still diagnostic evidence, not investment authority.
Strong historical walk-forward metrics do not guarantee profitable future
trades.

## Governance Change Request Rule

Any change to the frozen VSEF v1 evaluation methods, metrics, or required
artifact evidence must be handled as a governance change request before it is
represented as accepted v1 scope. The request must document:

- Proposed change
- Reason
- Affected documents
- Affected runtime surfaces
- Evidence required
- Approval status

Unapproved evaluation changes remain excluded, deferred to v1.5/v2, or
documented targets that must be verified before claiming implementation support.

## Acceptance Criteria

- [x] Evaluation is time-series-safe.
- [x] Walk-forward role is explained.
- [x] Metrics are defined.
- [x] Required artifacts are listed.
- [x] No evaluation claim is made without artifact evidence.

## Related Governance Documents

- [VSEF v1 Architecture Freeze](../architecture/VSEF_v1_ARCHITECTURE.md)
- [VSEF v1 Model Registry](MODEL_REGISTRY.md)
- [VSEF v1 Data Policy](DATA_POLICY.md)
- [VSEF v1 Project Tracker](PROJECT_TRACKER.md)
