# Training Pipeline: Label Integration
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Workflow guide |
| Created / authored | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `8800ce6e3780c7978856737e70cb5e3b999eacee` |
| Timestamp source | current metadata standardization run |
| Status | Active |

This document describes how to use the expanded training pipeline to train models on various label types (binary, ternary, regression, volatility) using the `src/ml/labels` package.

## Overview

The training script `scripts/train_ml_tickers.py` now supports a `--label-mode` argument. This allows the system to depart from the hard-coded multi-horizon targets and instead use any label generator registered in the `src/ml/labels` package.

## Supported Label Modes

| Mode | Registry Key | Task Type | Description |
| :--- | :--- | :--- | :--- |
| `binary_1d` | `cls_1d_updown` | Classification | 1-day forward return > 0 |
| `binary_5d` | `cls_5d_updown` | Classification | 5-day forward return > 0 |
| `ternary_1d` | `cls_1d_3class` | Classification | Up/Sideways/Down (1-day) |
| `ternary_5d` | `cls_5d_3class` | Classification | Up/Sideways/Down (5-day) |
| `regression_5d` | `reg_5d_return` | Regression | Continuous 5-day return |
| `volatility_5d` | `future_realized_vol_5d` | Regression | 5-day annualized realized volatility |

## Usage Examples

### 1. Default (Legacy) Training
Trains the standard 3-horizon ensemble (5d, 20d, 120d) with hard-coded thresholds.
```bash
python scripts/train_ml_tickers.py --tickers FPT --daily data/daily_market_split_data
```

### 2. Binary Classification (1-day)
Trains a single binary model (Up vs. Down) for the next day.
```bash
python scripts/train_ml_tickers.py --tickers FPT --label-mode binary_1d
```

### 3. Regression (5-day Return)
Trains a regressor to predict the actual percentage return over the next 5 days.
```bash
python scripts/train_ml_tickers.py --tickers FPT --label-mode regression_5d
```

## Model Storage

When using a custom `--label-mode`, the resulting models and feature lists are saved with a mode-specific suffix to avoid overwriting the default production models:

- **Classification**: `models/<TICKER>/trend_classifier_<mode>.joblib`
- **Regression**: `models/<TICKER>/regressor_<mode>.joblib`
- **Feature List**: `models/<TICKER>/feature_cols_<mode>.joblib`

## Implementation Details

- **Adapter**: `src/ml/labels/training_adapter.py` maps CLI modes to the registry.
- **Training Logic**: When a mode is selected, the script uses a specialized `_train_custom_label` function that handles both classification and regression tasks, including feature selection and performance logging.
- **Weights**: Both legacy and custom paths use recency and volatility-based sample weighting for robust training.
