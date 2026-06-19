# Experiment Tracking
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance note |
| Created / authored | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `8800ce6e3780c7978856737e70cb5e3b999eacee` |
| Timestamp source | current metadata standardization run |
| Status | Active |

Lightweight experiment tracking system for the VN100 stock prediction pipeline.

## Overview

The `ExperimentTracker` module in `src/ml/experiment_tracker.py` is used to log training metadata, hyperparameters, and performance metrics for each ticker's training run. This allows for comparing models across different versions of features or labels.

## Data Storage

Experiments are stored in a JSONL file at `reports/experiments.jsonl`. Each line is a valid JSON object representing a single run.

## Metrics Tracked

| Metric | Description |
| :--- | :--- |
| `run_id` | Unique 8-character ID for the training session. |
| `ticker` | Stock symbol (e.g., FPT, HPG). |
| `label_type` | The label configuration used (e.g., `binary_3d`). |
| `model_type` | Model architecture (e.g., `Ensemble_Stacking`). |
| `feature_count` | Number of features selected after pruning. |
| `metrics` | Dictionary of accuracy, MAE, and elite signal metrics. |
| `train_start` | Timestamp when training began. |
| `train_end` | Timestamp when training completed. |
| `model_path` | Directory containing the saved model artifacts. |

## Usage

The tracker is automatically initialized and used in `scripts/train_ml_tickers.py`. To view the latest experiments using command line:

```bash
tail -n 10 reports/experiments.jsonl | jq
```
