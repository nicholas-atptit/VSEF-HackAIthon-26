# VN100 Batch Inference
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

The VN100 Batch Inference mode allows the system to generate predictions for the entire VN100 (plus selected Viettel) universe in a single run. This is optimized for daily reporting and large-scale performance monitoring.

## Features

- **Dynamic Universe**: Automatically loads the current VN100 constituents using `get_vn100_universe()`.
- **Parallel Processing**: Uses asynchronous tasks with a semaphore to process multiple tickers simultaneously.
- **Comprehensive Predictions**:
    - **Trend Classification**: Directional probabilities (Up/Sideways/Down).
    - **Price Regression**: Quantile-based expected ranges (Bottom 10th, Median, Ceiling 90th).
    - **Volatility**: Annualised future realised volatility (if models available).
- **Structured Reporting**: Saves a detailed JSON report for each batch run.

## Usage

To run a full VN100 batch inference once:

```bash
python scripts/per_session_predict.py --batch --vn100
```

### Arguments

| Argument | Description |
| :--- | :--- |
| `--batch` | Enables batch mode and structured JSON reporting. |
| `--vn100` | Filters the universe to VN100 + Viettel tickers. |
| `--limit <N>` | (Optional) Limit the run to the first N tickers found with models. |
| `--tickers AAA,SSI` | (Optional) Run batch mode only for a specific subset. |

## Output

### Latest Predictions (Cache)
The latest results for every ticker are always maintained in:
`data/latest_predictions.json`

### Batch Reports
Each batch run generates a unique report in:
`data/processed/batch_inference_<YYYYMMDD>_<HHMMSS>.json`

#### Report Schema
```json
{
    "timestamp": "2026-04-01T10:50:00+07:00",
    "elapsed_sec": 45.2,
    "total_tickers": 103,
    "success_count": 98,
    "predictions": {
        "SSI": {
            "trend_probabilities": { ... },
            "expected_range": { ... },
            "volatility": 0.25,
            "horizon": "short"
        },
        ...
    }
}
```

## Troubleshooting

- **`model_not_found`**: Ensure `scripts/train_ml_tickers.py` has been run for that ticker.
- **`insufficient_data`**: The system requires at least 30 days of historical data in `raw_prices` or CSV to generate features.
