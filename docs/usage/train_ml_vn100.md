# VN100 Batch Training Guide
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

This document describes how to use the extended `scripts/train_ml_tickers.py` for batch training of the VN100 universe.

## Features
- **Dynamic Universe**: Automatically fetches current VN100 constituents plus 4 Viettel tickers (`VTP`, `VGI`, `CTR`, `FOX`).
- **Optimal Throughput**: Skips tickers that already have trained models unless forced.
- **Date Filtering**: Allows training on specific historical windows or recent data.
- **Dry Run Mode**: Preview which tickers will be processed.
- **Summary Reporting**: Generates a detailed JSON summary in `logs/` for every batch run.

## Usage

### 1. Basic Batch Training
Train all VN100 tickers that don't have models yet:
```bash
python scripts/train_ml_tickers.py --vn100
```

### 2. Force Retraining
Retrain all VN100 tickers even if models exist:
```bash
python scripts/train_ml_tickers.py --vn100 --retrain-existing
```

### 3. Date Restricted Training
Train only using data from 2024 onwards:
```bash
python scripts/train_ml_tickers.py --vn100 --start-date 2024-01-01
```

### 4. Limited Batch (Testing)
Train only the first 5 tickers of the VN100:
```bash
python scripts/train_ml_tickers.py --vn100 --max-tickers 5
```

### 5. Dry Run
Verify the batch scope without training:
```bash
python scripts/train_ml_tickers.py --vn100 --dry-run
```

## Configurable Options

| Option | Alias | Description |
|---|---|---|
| `--vn100` | - | Use dynamic VN100 + Viettel universe. |
| `--label-mode` | `--label-type` | Specify target label (e.g., `binary_1d`, `regression_5d`). |
| `--start-date` | - | Data filter start (YYYY-MM-DD). |
| `--end-date` | - | Data filter end (YYYY-MM-DD). |
| `--max-tickers` | - | Limit number of tickers to process. |
| `--retrain-existing`| - | Overwrite existing models in `models/`. |
| `--dry-run` | - | Smoke test mode. |

## Outputs
- **Models**: `models/<TICKER>/`
- **Evaluation Report**: `models/evaluation_report.csv`
- **Session Summary**: `logs/train_summary_<timestamp>.json`
