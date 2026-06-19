# VSEF v1 Model Registry

## Document Metadata

| Field | Value |
| --- | --- |
| Document name | VSEF v1 Model Registry |
| Phase | 0 |
| Status | Frozen for v1 |
| Last updated date | 2026-05-09 |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Owner | Project team / maintainer |
| Document type | Governance registry |

## Purpose

This registry defines the only forecasting models officially supported in the
frozen VSEF v1 scope. It gives reviewers and developers a single reference for
which models may be claimed as VSEF v1 models, what they are used for, and which
model families are outside scope.

This document is governance evidence only. It does not add a model, train a
model, change a runtime registry, or change evaluation behavior.

## Supported v1 Models

Only the following models are supported in VSEF v1:

| Model | Category | v1 status | Main purpose | Expected output | Notes / restrictions |
| --- | --- | --- | --- | --- | --- |
| SARIMAX | Statistical time-series model | Frozen v1 supported | Classical time-series comparator for daily OHLCV forecasting | Forecast rows, evaluation metrics, model manifest entries | Requires implementation and dependency evidence before production-readiness claims. |
| ETS | Statistical time-series model | Frozen v1 supported | Exponential smoothing comparator for daily OHLCV forecasting | Forecast rows, evaluation metrics, model manifest entries | Requires implementation and dependency evidence before production-readiness claims. |
| XGBoost | Gradient boosting model | Frozen v1 supported | Nonlinear tabular forecasting over engineered features | Forecast rows, evaluation metrics, model manifest entries | Optional dependency availability must be recorded when unavailable. |
| LightGBM | Gradient boosting model | Frozen v1 supported | Nonlinear tabular forecasting over engineered features | Forecast rows, evaluation metrics, model manifest entries | Optional dependency availability must be recorded when unavailable. |
| LSTM | Sequence deep learning model | Frozen v1 supported | Sequence-aware daily forecasting where sequence inputs are available | Forecast rows, training summary, model artifact, manifest entries | Must not be expanded into unrelated deep learning architectures under v1. |
| BiLSTM | Sequence deep learning model | Frozen v1 supported | Bidirectional sequence-aware daily forecasting where sequence inputs are available | Forecast rows, training summary, model artifact, manifest entries | Must not be expanded into unrelated deep learning architectures under v1. |
| Stacking | Ensemble / consensus layer | Frozen v1 supported | Combine prior model outputs in a time-series-safe ensemble layer | Stacking predictions, comparison metrics, manifest entries | Stacking is an ensemble layer, not a separate magic solution or investment authority. |

## Model Restrictions

- No new models may be added to VSEF v1 without governance approval.
- Experimental models must go to the v1.5/v2 backlog before they are evaluated
  for inclusion.
- LLMs are not forecasting models in VSEF v1.
- LLM explanations, if present, must remain optional and post-decision only.
  They may explain already generated diagnostic artifacts, but they may not
  create autonomous trading decisions.
- Failed model runs must not crash the whole pipeline if the current code
  already supports graceful fallback. Failures should be recorded in model
  execution logs, skipped-model records, manifests, or equivalent evidence.
- A model may not be claimed as production ready without artifact evidence for
  the dataset, ticker, horizon, date window, configuration, metrics, and model
  manifest.

## Excluded Models for v1

The following model classes are excluded from VSEF v1:

- Reinforcement learning models
- Transformers for price forecasting unless already implemented and approved
- Agentic autonomous trading models
- Intraday high-frequency models
- New deep learning models outside LSTM/BiLSTM
- New tree, linear, neural, or statistical model families not listed in the
  supported v1 model table

## Existing Non-v1 Model Surfaces

The repository contains older or broader model surfaces in some code paths and
documents. Phase 0 does not delete them, but it does freeze their governance
classification for v1 claims:

| Existing surface | v1 governance classification | Notes |
| --- | --- | --- |
| CART or decision-tree model paths | Legacy / archive candidate unless separately approved | Not in the frozen supported v1 model list. |
| Random forest forecast paths | Legacy / archive candidate or v1.5 backlog | Not in the frozen supported v1 model list. |
| Naive and moving-average baselines | Baseline evidence only, not supported v1 forecasting models | May be useful for comparison, but not official v1 supported models. |
| Linear, ridge, and lasso paths | Legacy / archive candidate or shadow evidence | Not in the frozen supported v1 model list. |
| Transformer, RL, or agentic model ideas | v2 / out of v1 | Must not enter v1 without governance approval. |

Implementation evidence should be verified before claiming production readiness.

## Governance Change Request Rule

Any change to the frozen VSEF v1 model scope must be handled as a governance
change request before the model is represented as supported v1 scope. The
request must document:

- Proposed change
- Reason
- Affected documents
- Affected runtime surfaces
- Evidence required
- Approval status

Unapproved model changes remain excluded, deferred to v1.5/v2, or legacy/archive
candidates.

## Acceptance Criteria

- [x] Supported models are frozen.
- [x] Unsupported models are clearly excluded.
- [x] Stacking is described as an ensemble layer, not a separate magic solution.
- [x] Registry is readable by a non-developer reviewer.

## Related Governance Documents

- [VSEF v1 Architecture Freeze](../architecture/VSEF_v1_ARCHITECTURE.md)
- [VSEF v1 Data Policy](DATA_POLICY.md)
- [VSEF v1 Evaluation Protocol](EVALUATION_PROTOCOL.md)
- [VSEF v1 Project Tracker](PROJECT_TRACKER.md)
