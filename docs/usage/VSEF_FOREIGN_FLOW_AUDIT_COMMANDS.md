# VSEF Foreign-Flow Audit Commands
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Workflow guide |
| Created / authored | Monday, 2026-04-27 00:00:00 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `8800ce6e3780c7978856737e70cb5e3b999eacee` |
| Timestamp source | existing document date |
| Status | Active |

## Purpose

This note records the supported command pattern for running walk-forward governance audits with an explicit curated foreign-flow artifact.

The command is for data-governance review only. It does not add model families, change model governance status, or claim trading-performance improvement.

## Foreign-Flow Modes

The walk-forward runner supports `--foreign-flow-mode auto|path|disabled`:

- `auto`: preserves existing default loader behavior.
- `path`: requires `--foreign-flow-path`.
- `disabled`: skips foreign-flow artifact loading and records intentional exclusion in metadata.

## Walk-Forward Audit With Curated Foreign Flow

Use `--foreign-flow-mode path` with `--foreign-flow-path` to pass a governed artifact without replacing the ignored default `data/foreign_flow.csv`:

```bash
python scripts/run_walkforward_all_models_stacking_eval.py --tickers SSI FPT ACB HPG --history-start 2020-12-21 --history-end 2025-02-28 --initial-train-start 2020-12-21 --initial-train-end 2024-12-31 --forecast-start 2025-01-02 --forecast-end 2025-01-24 --horizons short_5d --step-sizes 1 --algorithms cart,xgboost,lightgbm --foreign-flow-mode path --foreign-flow-path data/foreign_flow_curated.csv --output-dir outputs/walkforward_governance_audit_foreign_flow_real --max-workers 1 --max-depth 3 --meta-min-samples 1 --epochs 1
```

If `--foreign-flow-path` is omitted, the runner keeps the existing default foreign-flow loader behavior.

If a supplied path is missing, the run should fail clearly instead of silently falling back to the default fixture/cache path.

## Walk-Forward Audit With Foreign Flow Disabled

Use disabled mode for long-window audits where no governed artifact covers the requested tickers and dates:

```powershell
python scripts/run_walkforward_all_models_stacking_eval.py --tickers SSI FPT BVH VNM --history-start 2010-01-01 --history-end 2025-12-31 --initial-train-start 2010-01-01 --initial-train-end 2022-12-31 --forecast-start 2023-01-01 --forecast-end 2025-12-31 --horizons short_5d --step-sizes 1 --algorithms cart,xgboost,lightgbm --ohlcv-data-dir tmp/ohlcv_15y_refresh_probe_data --foreign-flow-mode disabled --output-dir outputs/walkforward_15y_daily_ssi_fpt_bvh_vnm_no_foreign_flow --max-workers 1 --max-depth 3 --meta-min-samples 5 --epochs 1
```

Disabled mode is an intentional exclusion marker. It is not complete foreign-flow coverage and foreign-flow features should not be interpreted.

## Metadata

The run metadata records:

- supplied foreign-flow path
- whether the path was explicit
- loaded row count
- loader source name and provenance
- artifact validation result for the forecast window
- disabled mode and reason, when foreign-flow is intentionally excluded

## Interpretation

Provider-backed rows are evidence only for the ticker/date pairs they cover. A `partial_coverage` artifact can be useful for source-row governance checks, but it should not be treated as broad foreign-flow coverage or trading-performance evidence.

Generated provider CSVs and walk-forward output folders should remain untracked unless explicitly approved for repository inclusion.
