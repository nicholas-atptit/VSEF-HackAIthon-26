# VSEF Foreign-Flow Disable Mode
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance note |
| Created / authored | Monday, 2026-04-27 23:29:57 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `8800ce6e3780c7978856737e70cb5e3b999eacee` |
| Timestamp source | Git history |
| Status | Active |

## Purpose

This note documents the walk-forward runner option for intentionally disabling foreign-flow context loading when no usable long-window foreign-flow artifact exists.

The mode is a data-governance and workflow clarity control. It does not add model families, change model governance status, fabricate foreign-flow rows, or support trading-performance claims.

## Modes

| mode | behavior |
| --- | --- |
| `auto` | Preserves existing behavior. If no explicit path is supplied, the default loader path is used. |
| `path` | Requires `--foreign-flow-path` and fails clearly if the path is missing. |
| `disabled` | Skips all foreign-flow artifact loading, including the default `data/foreign_flow.csv`, and records that foreign-flow context was intentionally disabled. |

Existing `--foreign-flow-path` usage remains supported. Use `--foreign-flow-mode path` when a governed artifact is required for a run.

## When To Use Disabled Mode

Use `--foreign-flow-mode disabled` for long-window audits where:

- no governed artifact covers the requested tickers and date range
- the local default `data/foreign_flow.csv` is only a fixture or scratch cache
- foreign-flow features should not be interpreted for the audit
- breadth and other context diagnostics should still be retained

Disabled mode is not the same as complete foreign-flow coverage. It means foreign-flow context is intentionally excluded from the run.

## Metadata

When disabled, run metadata records:

```json
{
  "foreign_flow_context": {
    "enabled": false,
    "mode": "disabled",
    "path": null,
    "row_count": 0,
    "source_name": "disabled",
    "artifact_validation": null,
    "reason": "foreign-flow context intentionally disabled"
  }
}
```

Additional backward-compatible fields such as `foreign_flow_path` and `foreign_flow_path_explicit` may also be present.

## Context Coverage

Disabled mode writes explicit diagnostic markers:

- `foreign_flow_context_mode = disabled`
- `foreign_flow_coverage_status = disabled`

For disabled foreign-flow context, coverage diagnostics set foreign-flow available and missing counts to zero and leave foreign-flow missing rates as unavailable. If breadth coverage is otherwise acceptable, disabled foreign-flow does not create a `weak_coverage` warning.

Actual missingness is still reported normally in `auto` and `path` modes.

## Feature Safety

Disabled mode does not create synthetic `foreign_*` feature values and does not load fixture rows from the default local cache. Support and provenance columns remain excluded from active model features.

Other context sources, including breadth, remain available when supplied by the existing pipeline.

## Command Examples

Long-window audit with foreign-flow intentionally disabled:

```powershell
python scripts/run_walkforward_all_models_stacking_eval.py --tickers SSI FPT BVH VNM --history-start 2010-01-01 --history-end 2025-12-31 --initial-train-start 2010-01-01 --initial-train-end 2022-12-31 --forecast-start 2023-01-01 --forecast-end 2025-12-31 --horizons short_5d --step-sizes 1 --algorithms cart,xgboost,lightgbm --ohlcv-data-dir tmp/ohlcv_15y_refresh_probe_data --foreign-flow-mode disabled --output-dir outputs/walkforward_15y_daily_ssi_fpt_bvh_vnm_no_foreign_flow --max-workers 1 --max-depth 3 --meta-min-samples 5 --epochs 1
```

The audit report for this command is `docs/audits/VSEF_15Y_DAILY_WALKFORWARD_NO_FOREIGN_FLOW_AUDIT.md`.

The multi-horizon follow-up using the same disabled-mode policy is `docs/audits/VSEF_15Y_MULTIHORIZON_WALKFORWARD_AUDIT.md`.

Run with a required curated artifact:

```powershell
python scripts/run_walkforward_all_models_stacking_eval.py --tickers SSI FPT ACB HPG --foreign-flow-mode path --foreign-flow-path data/foreign_flow_curated.csv --horizons short_5d --step-sizes 1 --algorithms cart,xgboost,lightgbm
```

## Interpretation Rules

- Disabled mode means foreign-flow is excluded and must not be interpreted.
- Complete OHLCV coverage does not imply complete foreign-flow coverage.
- Context coverage output remains research/evaluation evidence, not trading-performance proof.
- Generated outputs and provider CSVs should remain untracked unless explicitly approved.
