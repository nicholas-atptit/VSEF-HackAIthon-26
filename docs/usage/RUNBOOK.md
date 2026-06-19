# Offline Research Runbook

This runbook reproduces VSEF diagnostics from existing local historical/cache data. It does not authorize live-data fetches, provider API calls, heavy benchmark reruns, BUY/SELL output, or production operation.

## Default Mode and Authority

- Use `--offline-historical-only` for the forecast-engine workflows below.
- Model selection uses validation rows only; final rows are scoring-only.
- Output is offline diagnostic evidence, not investment advice or trading authority.
- Index coverage depends on local cache. `VNXALL` is skipped and recorded when no local cache exists.

## Safe Validation

```powershell
python scripts/check_repo_hygiene.py
python scripts/check_runtime_preflight.py
python scripts/check_provider_usage_policy.py
python -m pytest tests/data/test_provider_usage_policy.py -q
python -m pytest tests/data/test_vn_price_gateway_contract.py -q
python -m pytest tests/ml/test_directional_accuracy_metrics.py -q
python -m pytest tests/governance tests/evaluation tests/features tests/forecasting -q
```

These commands should not fetch live data or run heavy research benchmarks.

## Offline Forecast Engine

The runner reads existing local caches and writes forecast panels and evaluations to `reports/generated/vn_forecast_engine_v1/`, with summaries under `reports/results/` and a claim boundary under `reports/claims/`.

### Forecast Latest Local Cache

```powershell
python scripts/research/run_vn_forecast_engine_v1.py --offline-historical-only --forecast-latest --frequency hourly --horizons 5 --index-codes VNINDEX,VN30,HNXINDEX,HNX30,UPCOMINDEX,VNXALL
```

Generates a latest-cache offline forecast panel. It does not fetch live data or emit BUY/SELL output.

### Forecast From a Historical As-Of Timestamp

```powershell
python scripts/research/run_vn_forecast_engine_v1.py --offline-historical-only --forecast-asof "2025-01-02 10:00:00" --frequency hourly --horizons 5,10,20,40,60 --index-codes VNINDEX,VN30,HNXINDEX,HNX30,UPCOMINDEX,VNXALL
```

Simulates the information available at the historical cutoff. Actual fields are filled only when later local rows exist; otherwise they remain pending/offline.

### Full Offline Run

```powershell
python scripts/research/run_vn_forecast_engine_v1.py --offline-historical-only --full-run --frequency hourly --horizons 5,10,20,40,60 --index-codes VNINDEX,VN30,HNXINDEX,HNX30,UPCOMINDEX,VNXALL --timeout-seconds 14400
```

Builds local panel data, evaluates direction/return-price/range/ranking diagnostics, selects using validation only, and writes forecast panels and evaluation reports.

### Evaluation-Only Run

```powershell
python scripts/research/run_vn_forecast_engine_v1.py --offline-historical-only --build-evaluate --frequency hourly --horizons 5,10,20,40,60 --index-codes VNINDEX,VN30,HNXINDEX,HNX30,UPCOMINDEX,VNXALL --timeout-seconds 14400
```

Evaluates available local historical data. It does not create a live or production system.

## Heavy Research Runners

Run these only under an approved written protocol:

```powershell
python scripts/research/run_vn30_qml_forecasting.py --help
python scripts/research/run_vn30_model_universe_direction_price_benchmark.py --help
```

Do not run them during ordinary validation, rerun benchmarks casually, or use final-period results for selection.

## Output Navigation

- Forecast Engine: `reports/generated/vn_forecast_engine_v1/`
- Forecast Engine reports: `reports/results/VN_FORECAST_ENGINE_V1_*`
- Forecast Engine claim boundary: `reports/claims/VN_FORECAST_ENGINE_V1_CLAIM_BOUNDARY.md`
- QML is excluded from the HackAIthon MVP scope.
- Model Universe: `reports/generated/vn30_model_universe_direction_price/`
- Active evidence index: `reports/_index/ACTIVE_EVIDENCE_INDEX.md`

QML is excluded from the HackAIthon MVP scope.

## Split and Claim Discipline

Use `src/governance/split_policy.py`. Feature and target timestamps must be inside the same period; boundary-crossing rows are unassigned. Final rows are scoring-only.

All outputs remain offline diagnostic research. No trading, profitability, BUY/SELL, recommendation, investment advice, live deployment, production, daily T+1, or VN100 claim is permitted without explicit evidence and governance.


