# VSEF Context Coverage Diagnostics
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance note |
| Created / authored | Sunday, 2026-04-26 00:00:00 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `8800ce6e3780c7978856737e70cb5e3b999eacee` |
| Timestamp source | existing document date |
| Status | Active |

## Purpose

This note documents walk-forward diagnostics for breadth and foreign-flow context coverage. The goal is to quantify how often context rows are available during each rolling forecast fold.

This is a governance and transparency change. It does not add model families, remove features, change model governance status, or claim improved trading performance.

## Why Missing-Context Rates Matter

Context features can be valid in principle but still weakly supported in a particular run if many forecast rows lack matching source data. Missing-context rates help distinguish:

- features backed by measured context rows
- features affected by missing-context fallback values
- runs where context coverage is too sparse for strong interpretation

These diagnostics complement the availability metadata columns added for breadth and foreign-flow joins.

## Output Files

The walk-forward all-model runner writes:

- `csv/context_coverage_diagnostics.csv`
- `csv/context_coverage_summary.csv`

The files are written in the same diagnostic CSV folder as linear coefficient diagnostics, feature-importance diagnostics, and feature governance review outputs.

## Fold-Level Schema

`context_coverage_diagnostics.csv` contains one row per ticker, fold, and horizon.

Columns:

- `ticker`
- `fold_id`
- `step_size`
- `forecast_sequence_index`
- `prediction_date`
- `horizon`
- `row_count`
- `breadth_available_count`
- `breadth_missing_count`
- `breadth_available_rate`
- `breadth_missing_rate`
- `foreign_flow_available_count`
- `foreign_flow_missing_count`
- `foreign_flow_available_rate`
- `foreign_flow_missing_rate`
- `foreign_flow_context_mode`
- `foreign_flow_coverage_status`
- `coverage_warning_level`
- `coverage_metadata_status`
- `coverage_note`
- `train_start`
- `train_end`
- `eval_start`
- `eval_end`

## Summary Schema

`context_coverage_summary.csv` aggregates fold-level rows by ticker and horizon.

Columns:

- `ticker`
- `horizon`
- `fold_count`
- `mean_breadth_missing_rate`
- `max_breadth_missing_rate`
- `mean_foreign_flow_missing_rate`
- `max_foreign_flow_missing_rate`
- `weak_coverage_fold_count`
- `review_fold_count`
- `overall_coverage_warning_level`

## Warning Levels

The warning rule is intentionally simple:

- `ok`: maximum missing rate is `<= 0.05`
- `review`: maximum missing rate is `> 0.05` and `<= 0.25`
- `weak_coverage`: maximum missing rate is `> 0.25`
- `metadata_unavailable`: required availability metadata columns are absent

The maximum missing rate is calculated across breadth and foreign-flow metadata when both are available.

## Disabled Foreign-Flow Mode

When the runner is invoked with `--foreign-flow-mode disabled`, foreign-flow context is intentionally excluded instead of loaded from the default local cache. Fold diagnostics record `foreign_flow_context_mode = disabled` and `foreign_flow_coverage_status = disabled`.

Disabled foreign-flow rows use zero available and missing counts, unavailable foreign-flow rates, and do not create a `weak_coverage` warning solely because foreign-flow is absent. Breadth missing rates still participate in the warning calculation. In `auto` and `path` modes, actual foreign-flow missingness is reported normally.

`docs/audits/VSEF_15Y_DAILY_WALKFORWARD_NO_FOREIGN_FLOW_AUDIT.md` shows this behavior in a long-window rerun: breadth missing rates remain `0.0`, foreign-flow rates are unavailable by design, and all context coverage folds remain `ok`.

`docs/audits/VSEF_15Y_MULTIHORIZON_WALKFORWARD_AUDIT.md` confirms the same disabled-mode behavior across multiple forecast horizons.

## Interpreting Breadth Missing Rate

`breadth_missing_rate` is the share of feature-frame rows in a fold where no exact-date breadth source row was joined. A high rate means breadth-derived features may contain fallback values and should not be interpreted as fully measured context evidence for that run.

## Interpreting Foreign-Flow Missing Rate

`foreign_flow_missing_rate` is the share of feature-frame rows in a fold where no exact ticker/date foreign-flow source row was joined. A high rate means `foreign_*` features may be sparse or unavailable in that run.

## Relationship To Feature Governance Review

Feature governance review flags breadth and `foreign_*` features for timing review. Coverage diagnostics add run-level evidence about how much source context was actually available. They should inform governance interpretation but do not automatically downgrade, upgrade, include, or exclude features.

## Limitations

- Coverage diagnostics measure availability metadata, not live provider release timestamps.
- High coverage does not prove absence of leakage.
- Low coverage does not prove a feature is invalid; it means stronger interpretation is not justified without more source review.
- These diagnostics do not prove causality or trading performance.

## Recommended Next Validation

- Track missing-context rates across a broader ticker set and longer walk-forward window.
- Add report-level summaries for high missing-rate folds.
- Review whether missing-context rates should be included in future governance dashboards, not model inputs.

## Follow-Up: Broader Governance Audit

`docs/audits/VSEF_BROADER_FEATURE_GOVERNANCE_AUDIT.md` applies these coverage diagnostics to a four-ticker cached-data audit. In that run, breadth coverage was complete for the selected window, while foreign-flow coverage was unavailable and remained a weak-coverage governance finding.

`docs/audits/VSEF_FOREIGN_FLOW_COVERAGE_INVESTIGATION.md` adds a targeted follow-up for that weak-coverage finding. It documents that the local foreign-flow artifact did not contain the audited tickers or date window.

`docs/governance/VSEF_FOREIGN_FLOW_ARTIFACT_POLICY.md` defines the schema and classification rules used to decide whether a foreign-flow artifact is suitable for interpreting `foreign_*` diagnostics for a requested window.
