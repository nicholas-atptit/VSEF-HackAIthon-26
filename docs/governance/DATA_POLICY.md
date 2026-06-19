# VSEF v1 Data Policy

## Document Metadata

| Field | Value |
| --- | --- |
| Document name | VSEF v1 Data Policy |
| Phase | 0 |
| Status | Frozen for v1 |
| Last updated date | 2026-05-09 |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Owner | Project team / maintainer |
| Document type | Governance policy |

## Data Provider Policy

The official VSEF v1 data provider is `vnstock_data`.

VSEF v1 uses daily OHLCV data. Other providers are not part of v1 unless they
are explicitly documented later through governance approval. Phase 0 does not
add a new provider, adapter, database table, API, or ingestion runtime.

Any repository code that references intraday data, alternative data, macro data,
news, or other expanded provider surfaces must not be used as evidence that
those sources are included in frozen VSEF v1.

## Standard Schema

VSEF v1 daily OHLCV data must conform to this schema:

| Field name | Data type expectation | Description | Validation rule |
| --- | --- | --- | --- |
| `date` | Date, datetime, or parseable date string | Trading date for the observation | Must be non-null, parseable, and sortable in chronological order. |
| `ticker` | String | Stock ticker symbol | Must be non-null, non-empty, and consistent within ticker-level processing. |
| `open` | Numeric | Opening price for the trading day | Must be numeric and non-negative; should be checked against `high` and `low` when possible. |
| `high` | Numeric | Highest price for the trading day | Must be numeric, non-negative, and greater than or equal to `low`. |
| `low` | Numeric | Lowest price for the trading day | Must be numeric, non-negative, and less than or equal to `high`. |
| `close` | Numeric | Closing price for the trading day | Must be numeric and non-negative; should be checked against `high` and `low` when possible. |
| `volume` | Numeric, preferably integer-like | Trading volume for the day | Must be numeric and non-negative; zero volume should be flagged or explained where material. |

The required schema is:

- `date`
- `ticker`
- `open`
- `high`
- `low`
- `close`
- `volume`

## Data Quality Rules

- Dates must be parseable and sorted.
- Duplicate ticker-date rows must be handled.
- OHLCV fields must be numeric.
- Empty datasets must be rejected or handled gracefully.
- Missing values must be documented or handled by the feature pipeline.
- Data must not be manually edited without documentation.
- Data leakage must be avoided.
- Future target values, future realized returns, or future feature values must
  not be available to a model at training or prediction time.
- Provider provenance should be retained where available.
- Any correction, backfill, or exclusion should be documented in a run
  manifest, log, data-quality note, or equivalent evidence.

## Data Frequency

VSEF v1 uses daily data.

Intraday data is excluded from VSEF v1. Weekly or monthly aggregation may be
used only if it is explicitly generated from daily data and documented in the
run configuration, training summary, manifest, or equivalent artifact evidence.

## Evidence Artifacts

Expected data evidence includes:

- `fetch_summary.csv`
- `training_summary.csv`
- `run_config.json`
- manifests
- logs where available

These are expected evidence paths or artifact classes. Phase 0 does not create
fake logs, fake CSVs, fake manifests, fake data fetches, or fake test results.

## Non-v1 Data Sources

| Data source or frequency | v1 status | Notes |
| --- | --- | --- |
| Intraday or hourly market data | Excluded from v1 | v1 uses daily OHLCV data only. |
| Broker execution feeds | Excluded from v1 | No broker execution is part of frozen v1. |
| Alternative data beyond current documented scope | Deferred to v1.5/v2 | Requires governance approval before inclusion. |
| Manually edited market data | Excluded unless documented | Manual changes must be reviewable and justified. |
| Non-`vnstock_data` providers | Excluded from v1 unless later governed | Provider expansion is not part of Phase 0. |

## Governance Change Request Rule

Any change to the frozen VSEF v1 data provider, schema, frequency, or validation
scope must be handled as a governance change request before it is represented as
accepted v1 scope. The request must document:

- Proposed change
- Reason
- Affected documents
- Affected runtime surfaces
- Evidence required
- Approval status

Unapproved data-source or schema changes remain excluded, deferred to v1.5/v2,
or out of scope.

## Acceptance Criteria

- [x] Data provider is frozen.
- [x] Schema is explicit.
- [x] Validation rules are documented.
- [x] Non-v1 data sources are excluded.

## Related Governance Documents

- [VSEF v1 Architecture Freeze](../architecture/VSEF_v1_ARCHITECTURE.md)
- [VSEF v1 Model Registry](MODEL_REGISTRY.md)
- [VSEF v1 Evaluation Protocol](EVALUATION_PROTOCOL.md)
- [VSEF v1 Project Tracker](PROJECT_TRACKER.md)
