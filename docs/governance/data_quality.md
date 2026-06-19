# Data Quality Validation
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

Daily data quality validation layer for the VN100 stock prediction system.

## Overview

The `DataQualityValidator` module in `src/validators/data_quality.py` provides automated checks for all data ingestion and training operations. It's integrated into the following scripts to ensure that models are trained on reliable data:

- `scripts/sync_all_data.py` (via `BackdateIngestor`)
- `scripts/train_ml_tickers.py`

## Validation Rules

The validator implements two main check categories:

### 1. OHLCV Validation

| Check | Description | Action |
| :--- | :--- | :--- |
| Missing Columns | Ensure all required fields (open, high, low, close, volume) exist. | Error (Raise) |
| Negative Values | Ensure prices and volume are non-negative. | Error (Raise) |
| High < Low | Ensure high price is always greater than or equal to low price. | Error (Raise) |
| Duplicate Dates | Ensure no two rows share the same date/time. | Error (Raise) |
| Zero Volume | Warn if more than 10% of records have 0 volume. | Warning |
| Empty Dataset | Detect empty DataFrames or null datasets. | Error (Raise) |

### 2. Feature Validation

| Check | Description | Action |
| :--- | :--- | :--- |
| Excessive Nulls | Warn if a feature has more than 20% NaN values after generation. | Warning |
| Infinite Values | Detect Inf or -Inf in the feature matrix. | Warning |

## Integration Nodes

### Ingestion (`BackdateIngestor`)
Validates newly fetched data from `vnstock` or other sources before committing to the database.

### Training (`train_ml_tickers.py`)
Validates the historical CSV loaded from the filesystem and additional checks on the final feature matrix before training begins.

## Usage example

```python
from src.validators.data_quality import DataQualityValidator

validator = DataQualityValidator(ticker="FPT")
success, issues = validator.validate_ohlcv(df, raise_on_error=False)
```
