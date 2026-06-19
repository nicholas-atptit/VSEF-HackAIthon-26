# Label Engineering — VN100 Daily Prediction Targets
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

## Overview

The `src/ml/labels/` package provides a **registry-based** label engineering
layer for the VN100 daily prediction pipeline.  Each label generator is a
self-contained class that computes one or more target columns from raw OHLCV
data, with **strict time-safety** guarantees (no look-ahead bias).

## Quick Start

```python
from src.ml.labels import get_generator, apply_all_labels

# ── Single label ──
gen = get_generator("cls_1d_updown")
df = gen.generate(ohlcv_df)

# ── All labels at once ──
df = apply_all_labels(ohlcv_df)

# ── Selective subset ──
df = apply_all_labels(ohlcv_df, names=["cls_1d_updown", "reg_next_close_return"])
```

## Available Labels

### Binary Classification

| Name | Column | Horizon | Description |
|------|--------|---------|-------------|
| `cls_1d_updown` | `label_cls_1d_updown` | 1 day | 1 if close goes up, 0 otherwise |
| `cls_5d_updown` | `label_cls_5d_updown` | 5 days | 1 if 5-day return > 0, 0 otherwise |
| `cls_20d_updown` | `label_cls_20d_updown` | 20 days | 1 if 20-day return > 0, 0 otherwise |

### Ternary Classification

| Name | Column | Horizon | Classes | Default Threshold |
|------|--------|---------|---------|-------------------|
| `cls_1d_3class` | `label_cls_1d_3class` | 1 day | 0=Up, 1=Sideways, 2=Down | ±1% |
| `cls_5d_3class` | `label_cls_5d_3class` | 5 days | 0=Up, 1=Sideways, 2=Down | ±2% |

### Regression Targets

| Name | Column | Horizon | Description |
|------|--------|---------|-------------|
| `reg_next_close_return` | `target_reg_next_close_return` | 1 day | Forward close-to-close return |
| `reg_5d_return` | `target_reg_5d_return` | 5 days | Forward 5-day return |

### Volatility Targets

| Name | Column | Horizon | Description |
|------|--------|---------|-------------|
| `future_realized_vol_5d` | `target_future_realized_vol_5d` | 5 days | Annualised realised vol over next 5 days |

## Time Safety

All label generators use `shift(-horizon)` to access **future** prices.
This means:

- Labels are fully time-safe — they never leak future information into
  current-row features.
- The **last `horizon` rows** in the output will have `NaN` label values.
  These rows must be dropped before training.
- At **inference time**, labels are not available — they are the prediction
  targets.

```
Row t:    features[t] computed from data[0..t]
          label[t]    computed from data[t+1..t+horizon]  ← future!
```

## Configurable Thresholds

Ternary classification thresholds can be configured via `config/settings.py`
or environment variables:

| Setting | Env Variable | Default | Used By |
|---------|-------------|---------|---------|
| `label_cls_1d_threshold` | `LABEL_CLS_1D_THRESHOLD` | `0.01` (1%) | `cls_1d_3class` |
| `label_cls_5d_threshold` | `LABEL_CLS_5D_THRESHOLD` | `0.02` (2%) | `cls_5d_3class` |

Override via `.env`:

```bash
LABEL_CLS_1D_THRESHOLD=0.015
LABEL_CLS_5D_THRESHOLD=0.025
```

Or pass directly:

```python
gen = Cls1d3Class(threshold=0.015)
```

## Architecture

```
src/ml/labels/
├── __init__.py          # Registry + apply_all_labels() + public API
├── base.py              # BaseLabelGenerator abstract class
├── classification.py    # Binary + ternary classification labels
├── regression.py        # Continuous return targets
└── volatility.py        # Realised volatility targets
```

### Registry

The `LABEL_REGISTRY` dict maps canonical name → generator class.  The
`get_generator(name)` factory function instantiates generators by name
and automatically injects settings-driven thresholds.

### Adding New Labels

1. Create a new class inheriting from `BaseLabelGenerator`
2. Implement `name`, `label_columns`, and `_compute(df)`
3. Register in `LABEL_REGISTRY` in `__init__.py`

```python
class MyNewLabel(BaseLabelGenerator):
    @property
    def name(self) -> str:
        return "my_new_label"

    @property
    def label_columns(self) -> list[str]:
        return ["target_my_new_label"]

    def _compute(self, df: pd.DataFrame) -> pd.DataFrame:
        df["target_my_new_label"] = df["close"].shift(-10) / df["close"] - 1
        return df
```

## Integration with Training Pipeline

Labels integrate with the existing ML pipeline:

```python
from src.ml.data_loader import generate_mock_data
from src.ml.feature_engineering import FeatureEngineer
from src.ml.labels import apply_all_labels

# 1. Load data
df = generate_mock_data("FPT", num_days=600)

# 2. Generate labels
df = apply_all_labels(df)

# 3. Feature engineering
fe = FeatureEngineer()
features_df = fe.transform(df)

# 4. Split features / targets
target_col = "label_cls_1d_updown"
X = fe.get_feature_columns(features_df)
y = features_df[target_col]

# 5. Drop NaN rows (from both horizon and rolling windows)
valid = y.notna()
X_train = features_df.loc[valid, X]
y_train = y[valid]
```

## Running Tests

```bash
python -m pytest tests/test_label_engineering.py -v
```
