# Feature Engineering — VN100 Daily Prediction Features
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

> **Module**: `src/ml/feature_engineering.py`  
> **Constant**: `VN100_DAILY_FEATURES`  
> **Method**: `FeatureEngineer._add_vn100_daily_features()`

## Overview

The VN100 daily feature set extends the existing `FeatureEngineer` with 19
standardised features designed for daily-resolution stock prediction across
the VN100 universe.  The features are computed **per ticker** and are
**time-safe** (no look-ahead bias).

---

## Feature Catalogue

### 1. Price-Level / Return Features

| Feature | Formula | Notes |
|---|---|---|
| `prev_close` | `close.shift(1)` | Previous session close price |
| `close_to_close_return_1d` | `close.pct_change(1)` | Alias for existing `pct_return` |
| `open_to_close_return_1d` | `(close - open) / open` | Intraday body return |
| `overnight_return_1d` | `(open - prev_close) / prev_close` | Gap / overnight return |
| `high_low_range_pct` | `(high - low) / close` | Daily range as % of close |
| `true_range` | `max(H-L, |H-prevC|, |L-prevC|)` | Wilder's True Range (scalar) |
| `atr_14` | `EMA(true_range, 14)` | **Pre-existing** — from `_add_volatility_features` |
| `return_3d` | `close.pct_change(3)` | 3-day rolling return |
| `return_5d` | `close.pct_change(5)` | Alias for existing `return_roll_5` |
| `return_10d` | `close.pct_change(10)` | 10-day rolling return |
| `return_20d` | `close.pct_change(20)` | Alias for existing `return_roll_20` |

### 2. Volume Features

| Feature | Formula | Notes |
|---|---|---|
| `volume_ma_5` | `volume.rolling(5).mean()` | 5-day volume moving average |
| `volume_ma_20` | `volume.rolling(20).mean()` | 20-day volume moving average |
| `volume_ratio_5` | `volume / volume_ma_5` | **Pre-existing** — from Step 4 |
| `volume_ratio_20` | `volume / volume_ma_20` | **Pre-existing** — from Step 4 |

### 3. Value (Turnover) Features

| Feature | Formula | Notes |
|---|---|---|
| `value_ratio_5` | `turnover / turnover.rolling(5).mean()` | Turnover = close × volume |
| `value_ratio_20` | `turnover / turnover.rolling(20).mean()` | Captures capital flow shifts |

### 4. Volatility Features

| Feature | Formula | Notes |
|---|---|---|
| `rolling_volatility_5` | `pct_return.rolling(5).std()` | Short-term return volatility |
| `rolling_volatility_20` | `pct_return.rolling(20).std()` | Medium-term return volatility |

---

## Existing vs. Newly Added Features

| Feature | Status |
|---|---|
| `prev_close` | **NEW** — previously an unnamed intermediate variable |
| `close_to_close_return_1d` | **ALIAS** → `pct_return` |
| `open_to_close_return_1d` | **NEW** — intermediate var `open_to_close_ret` was never stored |
| `overnight_return_1d` | **NEW** — intermediate var `overnight_ret` was never stored |
| `high_low_range_pct` | **NEW** |
| `true_range` | **NEW** — ATR existed but scalar TR did not |
| `atr_14` | **PRE-EXISTING** ✅ |
| `return_3d` | **NEW** |
| `return_5d` | **ALIAS** → `return_roll_5` |
| `return_10d` | **NEW** |
| `return_20d` | **ALIAS** → `return_roll_20` |
| `volume_ma_5` | **NEW** — was computed inline but never stored |
| `volume_ma_20` | **NEW** — was computed inline but never stored |
| `volume_ratio_5` | **PRE-EXISTING** ✅ |
| `volume_ratio_20` | **PRE-EXISTING** ✅ |
| `value_ratio_5` | **NEW** |
| `value_ratio_20` | **NEW** |
| `rolling_volatility_5` | **NEW** |
| `rolling_volatility_20` | **NEW** |

**Summary**: 4 pre-existing, 3 aliases, 12 genuinely new columns.

---

## Design Decisions

### No Duplication
Every feature is guarded by an `if "feature_name" not in df.columns` check.
If a previous step already created the column, the VN100 method skips it.

### Alias Strategy
Where the legacy pipeline computes an equivalent feature under a different
name (e.g. `pct_return`), the VN100 method creates a lightweight alias
rather than recomputing from scratch.  This ensures downstream code can
reference the canonical VN100 name without any numerical discrepancy.

### Ordering
`_add_vn100_daily_features` runs **after** all legacy feature groups
(volatility, momentum, structure, volume, advanced indicators, lagged,
rolling returns) so it can reference any column they produce.  It runs
**before** the final `dropna()` so that rows with insufficient warmup
data are correctly removed.

### Value (Turnover) Proxy
The `value_ratio_*` features use `close × volume` as a turnover proxy.
This is not the true VWAP-based turnover but provides a reasonable
approximation when intraday data is unavailable.

---

## Running Tests

```bash
# Run only VN100 feature tests
python -m pytest tests/test_feature_engineering_vn100.py -v

# Run all feature engineering tests (legacy + VN100)
python -m pytest tests/test_feature_engineering.py tests/test_feature_engineering_vn100.py -v
```

## Usage Example

```python
from src.ml.data_loader import generate_mock_data
from src.ml.feature_engineering import FeatureEngineer, VN100_DAILY_FEATURES

fe = FeatureEngineer()
df = generate_mock_data("FPT", num_days=300)
features = fe.transform(df)

# Verify all VN100 features are present
missing = [f for f in VN100_DAILY_FEATURES if f not in features.columns]
assert not missing, f"Missing features: {missing}"

# Use VN100 features for downstream ML
X = features[VN100_DAILY_FEATURES]
```
