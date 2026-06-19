# VSEF Context Availability Metadata
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

This note documents explicit availability metadata for breadth and foreign-flow context joins. The metadata is intended to make context timing and missing-data behavior easier to audit.

This is a research governance change. It does not add new model families, change model governance status, remove features, or claim improved trading performance.

## Why Missing Zero And Measured Zero Must Be Separated

Some breadth features can legitimately be zero. For example, `market_breadth`, `up_volume`, or `down_volume` can be measured as `0.0` on a date with available breadth data.

Before this change, a missing breadth join could also become `0.0` after the conservative numeric fill. That made two cases look identical:

- measured zero: source row exists and the value is actually zero
- missing fallback zero: no source row exists and the value was filled to zero

The new metadata columns separate these cases without changing the feature values themselves.

## Breadth Metadata Columns

When breadth context is requested through `apply_context_features`, the resulting frame includes:

- `breadth_context_available`: `True` when an exact same-date breadth row was joined
- `breadth_context_source_date`: the breadth source date used for the row; `NaT` when no exact source row was joined
- `breadth_context_missing`: `True` when no exact same-date breadth row was available

Breadth joins remain exact normalized-date joins. Future-dated breadth rows are not pulled backward.

## Foreign-Flow Metadata Columns

When foreign-flow context is requested through `apply_context_features`, the resulting frame includes:

- `foreign_flow_context_available`: `True` when an exact same-ticker and same-date foreign-flow row was joined
- `foreign_flow_context_source_date`: the foreign-flow source date used for the row; `NaT` when no exact source row was joined
- `foreign_flow_context_missing`: `True` when no exact ticker/date foreign-flow row was available

Foreign-flow joins remain ticker-scoped and exact-date. Future-dated foreign-flow rows are not pulled backward.

## Source-Date Policy

For breadth and foreign-flow joins, the source date is the context row's normalized `date` before merging. Because the join is exact-date, a populated source date should equal the ticker row date.

Macro and cross-asset context still use backward as-of alignment and are not changed by this task.

## Model-Feature Exclusion Policy

The metadata columns are support/governance columns. They are added to `NON_FEATURE_SUPPORT_COLUMNS` and are excluded from active model feature selection by `FeatureEngineer.get_feature_columns()`.

They should not become model inputs unless a later governed feature-selection decision explicitly allows that.

## Governance Review Impact

The feature governance review now references availability metadata in source hints and reasons for breadth and foreign-flow context features.

This does not automatically downgrade breadth or foreign-flow features to `safe_trailing`. They remain timing-review candidates because source-date availability and release timing still need governance.

Local OHLCV-derived flow features such as `turnover_ma_60` remain separate from joined context features.

## Limitations

- The metadata identifies exact-date join availability; it does not validate live provider release timestamps.
- A missing context row can still produce conservative filled values for legacy compatibility, so downstream reports should inspect the metadata before interpreting zeros.
- The tests use synthetic data and validate mechanics, not market performance.
- The metadata does not prove absence of leakage, causality, or tradable performance.

## Recommended Next Validation

- Add source-date or release-date contracts to cached breadth and foreign-flow artifacts where practical.
- Track missing-context rates in walk-forward diagnostics.
- Consider separate missingness features only after governance review, tests, and leakage checks justify using them as model inputs.

## Follow-Up: Coverage Diagnostics

`docs/governance/VSEF_CONTEXT_COVERAGE_DIAGNOSTICS.md` documents the follow-up walk-forward summaries for breadth and foreign-flow missing-context rates. These diagnostics measure coverage by ticker, fold, and horizon without adding the metadata columns to model features.

`docs/audits/VSEF_FOREIGN_FLOW_COVERAGE_INVESTIGATION.md` documents a cached-data follow-up where foreign-flow metadata correctly remained missing because the local source artifact did not cover the requested tickers or dates.

`docs/governance/VSEF_FOREIGN_FLOW_ARTIFACT_POLICY.md` documents how foreign-flow artifacts should be validated before availability metadata is interpreted as real source coverage.
