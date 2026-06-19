# Ranked Prediction Generation System
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

This document explains the implementation of the ranked prediction table generator for the VN100 stock forecasting system.

## 1. Motivation
The system already identifies daily signals, but for portfolio management, we need a way to **prioritize** assets. The ranked prediction generator (v1.0) provides a structured way to identify the best opportunities based on model conviction, expected return, and risk.

## 2. Infrastructure Enhancements
To support meaningful ranking, the underlying prediction payload was upgraded to version **5.1**.

### Schema Updates (`src/api/schemas_v2.py`)
- **`TechnicalForecast`**: Added `current_price` (float). 
- **`TechnicalHorizon`**: Added `volatility_score` (float).
These fields ensure that reports can calculate relative returns and sort by risk metrics without re-loading data from the database.

### Signal Generation (`src/ml/signal_generator.py`)
The `SignalGenerator.generate` method was updated to:
- Accept an optional `volatility_score`.
- Embed the `current_price` and `volatility_score` into the unified JSON payload.

### Batch Inference (`scripts/per_session_predict.py`)
The prediction loop now extracts the `volatility` predicted by the `DualModelTrainer` and passes it along to the signal generator.

---

## 3. Implementation Details: `src/reporting/ranked_predictions.py`

This module implements the core ranking logic.

### Tasks Carried Out:
1. **JSON Flattening**: Predictions are stored as nested JSON objects (v5.1). The generator flattens these into a `pandas.DataFrame` for efficient sorting.
2. **Ranking Algorithms**:
   - **`top_long_1d` / `top_long_5d`**: Ranked by `up` probability from the primary (usually 5-day) model.
   - **`top_expected_return`**: Calculated using $(P_{median\_target} / P_{current}) - 1$.
   - **`high_risk_volatility_names`**: Ranked by the regression-based volatility score.
3. **Multi-Format Export**:
   - **CSV**: Detailed per-rank tables saved to `reports/`.
   - **Markdown**: A consolidated summary for human review (also saved to `reports/`).

---

## 4. Usage

### Generate from latest cache:
```bash
python -m src.reporting.ranked_predictions
```

### Generate from the latest batch file in `data/processed/`:
```bash
python -m src.reporting.ranked_predictions --latest
```

### Options:
- `--file <path>`: Specify a custom predictions JSON.
- `--top <n>`: Show top N items (default 10).

---

## 5. Verification
- **Unit Tests**: Coverage for JSON loading, flattening, and ranking logic.
- **Payload Verification**: Confirmed that `per_session_predict.py` output contains the required `current_price` and `volatility_score`.
