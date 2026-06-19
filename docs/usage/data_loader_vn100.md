# VN100 Data Loader — `src/ml/data_loader.py` Extensions
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

> **Module**: `src.ml.data_loader`  
> **Version**: v2 (VN100 extensions)  
> **Date**: 2026-04-01

## Overview

The data loader has been extended to support building **batch daily datasets** for the
VN100 stock universe without breaking any existing interfaces.

### New Capabilities

| Function / Class | Purpose |
|---|---|
| `load_ohlcv_from_csv()` | Load daily OHLCV from per-ticker CSV files (file-backed fallback) |
| `load_market_proxy()` | Load the VNINDEX daily return proxy CSV |
| `load_fundamentals()` | Load fundamental data CSV with optional ticker filter |
| `load_sentiment()` | Load sentiment/news features with date and ticker filters |
| `VN100DataLoader` | Class for batch-loading across multiple tickers with automatic fallback |
| `load_vn100_daily_dataset()` | One-call convenience wrapper for the full VN100 universe |

### Preserved Interfaces (Backward Compatible)

| Function | Status |
|---|---|
| `load_ohlcv_from_db()` | ✅ Unchanged |
| `load_ohlcv_from_vnstock()` | ✅ Unchanged |
| `generate_mock_data()` | ✅ Unchanged |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              load_vn100_daily_dataset()                  │  ← One-call API
│                        │                                │
│                VN100DataLoader                          │  ← Batch orchestrator
│                   │      │                              │
│          build_dataset() │ build_inference_dataset()    │
│                   │                                     │
│        ┌──────────┼──────────┐                         │
│  load_ohlcv_   load_ohlcv_  load_ohlcv_               │
│  from_csv()    from_db()    from_vnstock()             │
│        │                                                │
│  load_market_proxy()  load_fundamentals()              │
│  load_sentiment()                                       │
└─────────────────────────────────────────────────────────┘
```

### Data Source Priority

The `VN100DataLoader` uses a configurable fallback chain:

| `prefer_source` | Order |
|---|---|
| `"csv"` (default) | CSV → TimescaleDB → vnstock API |
| `"db"` | TimescaleDB → CSV → vnstock API |

---

## Usage Examples

### 1. Load dataset for specific tickers

```python
import datetime as dt
from src.ml.data_loader import VN100DataLoader

loader = VN100DataLoader()
df = loader.build_dataset(
    tickers=["FPT", "HPG", "VNM"],
    start_date=dt.date(2022, 1, 1),
    end_date=dt.date(2024, 12, 31),
    join_market=True,
)
print(df.shape)
# → (3000+, 8)  with columns: date, open, high, low, close, volume, ticker, m_ret
```

### 2. Load the full VN100 universe

```python
from src.ml.data_loader import load_vn100_daily_dataset

df = load_vn100_daily_dataset(
    start_date=dt.date(2023, 1, 1),
    join_market=True,
    join_fundamentals=True,
)
```

### 3. Build an inference dataset (latest data)

```python
from src.ml.data_loader import VN100DataLoader

loader = VN100DataLoader()
df = loader.build_inference_dataset(
    tickers=["FPT", "HPG", "VNM"],
    lookback_days=120,  # ~6 months of data
)
```

### 4. Load a single ticker from CSV

```python
from src.ml.data_loader import load_ohlcv_from_csv
import datetime as dt

df = load_ohlcv_from_csv(
    "SSI", 
    start_date=dt.date(2023, 1, 1), 
    end_date=dt.date(2023, 12, 31)
)
```

### 5. Integrate with the existing feature engineering pipeline

```python
from src.ml.data_loader import VN100DataLoader
from src.ml.feature_engineering import FeatureEngineer

loader = VN100DataLoader()
fe = FeatureEngineer()

for ticker in ["FPT", "HPG"]:
    raw_df = loader._load_single(ticker)
    feat_df = fe.transform(raw_df)
    print(f"{ticker}: {feat_df.shape}")
```

---

## Output DataFrame Schema

All datasets returned by `VN100DataLoader` have a consistent schema:

| Column | Type | Description |
|---|---|---|
| `date` | `datetime64` | Trading date (normalised to midnight) |
| `open` | `float64` | Open price |
| `high` | `float64` | High price |
| `low` | `float64` | Low price |
| `close` | `float64` | Close price |
| `volume` | `int64` | Trading volume |
| `ticker` | `str` | Stock symbol (uppercase) |
| `m_ret` | `float64` | *(optional)* Market proxy daily return |

Additional columns from fundamentals or sentiment joins preserve their original names.

---

## File Paths

| Data | Default Path |
|---|---|
| Per-ticker CSVs | `data/daily_market_split_data/<TICKER>.csv` |
| Market proxy | `data/market_proxy.csv` |
| Fundamentals | `data/fundamentals_latest.csv` |
| Sentiment | `data/sentiment_features.csv` |

All paths are configurable via function arguments.

---

## Testing

Run the smoke tests:

```bash
python -m pytest tests/test_data_loader_vn100.py -v
```

The tests cover:
- Backward compatibility (original APIs unchanged)
- CSV loading with date filtering
- Missing ticker handling (returns empty DataFrame)
- Batch dataset building
- Market proxy joining
- DataFrame schema validation
- Inference dataset generation

---

## Assumptions

1. **CSV format**: Per-ticker CSVs follow the existing `time,open,high,low,close,volume,ticker` format produced by `scripts/extract_daily_csv.py`.
2. **TimescaleDB availability**: DB loading is tried but failure is graceful — falls back to CSV.
3. **Market proxy**: Uses the existing `data/market_proxy.csv` with `[date, m_ret]` columns.
4. **No vnstock API invention**: The vnstock fallback reuses the existing `load_ohlcv_from_vnstock()` function.
5. **Fundamentals/sentiment**: These are optional joins; missing files cause no errors.
