# Daily Ingestion Flow for VN100
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

This document describes the enhanced daily ingestion system for the VN100 stock universe. The system provides a unified entry point for fetching historical and daily price data, market benchmarks, and local raw storage.

## Entry Point

The primary script for data synchronization is:
`scripts/sync_all_data.py`

## Usage Examples

### 1. Default Daily Update
Syncs the default ticker universe (VIP list or legacy VN100) for the last 180 days, resuming from the last known date in the database.
```bash
python scripts/sync_all_data.py
```

### 2. VN100 Daily Sync
Syncs the current VN100 constituents fetched dynamically from the market.
```bash
python scripts/sync_all_data.py --universe_mode current_vn100
```

### 3. Historical Backfill with Benchmark
Syncs a specific date range for the VN100 universe and includes the VNINDEX benchmark.
```bash
python scripts/sync_all_data.py --universe_mode current_vn100 --start_date 2023-01-01 --end_date 2023-12-31 --benchmark
```

### 4. Force Refresh and Save Raw Copies
Ignores database progress and saves a local CSV copy of all fetched data for audit or offline analysis.
```bash
python scripts/sync_all_data.py --universe_mode current_vn100 --force_refresh --save_raw_copy
```

## CLI Arguments Reference

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--universe_mode` | Selection of ticker universe: `all` (VIP list) or `current_vn100` (Dynamic). | `all` |
| `--start_date` | Start date for ingestion (YYYY-MM-DD). | 180 days ago |
| `--end_date` | End date for ingestion (YYYY-MM-DD). | Today |
| `--force_refresh` | If set, ignores existing database progress and fetches the full range. | False |
| `--save_raw_copy` | If set, saves each ticker's data to `data/raw/<ticker>_<date>.csv`. | False |
| `--benchmark` | If set, also synchronizes the `VNINDEX` market benchmark. | False |
| `--vn100` | (Legacy) Flag to use the hardcoded VN100 + Viettel list. | False |

## Monitoring and Logs

The system uses structured logging via `structlog`. Logs are output to the console (standard out) and can be found in the `logs/` directory if configured.

At the end of each run, a summary is displayed:
```text
==================================================
SYNC SUMMARY
Tickers Processed: 104
Total Rows Ingested: 2450
Benchmark Rows: 22
Date Range: 2024-03-01 to 2024-04-01
Raw copies saved to: data/raw/
==================================================
```

## Troubleshooting

- **Rate Limits**: The system includes a 1-second cooldown per ticker and uses a semaphore to limit concurrent requests. If you encounter rate limit errors, consider increasing the delay in `src/historical/backdate.py`.
- **API Failures**: Per-ticker failures are logged but do not stop the entire process. Check the logs for `backdate_ticker_error`.
- **Database Connection**: Ensure TimescaleDB is running and the connection string in `config/settings.py` is correct.
