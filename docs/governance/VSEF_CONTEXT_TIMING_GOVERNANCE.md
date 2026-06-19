# VSEF Context Timing Governance
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

This note documents timing assumptions for market breadth and flow-style context features flagged by the real feature governance audit. The goal is to make source-date alignment and forward-fill behavior explicit before using these features as stronger model-governance evidence.

This is a research governance note. It does not remove features, promote models, or claim improved trading performance.

## Features Reviewed

The preceding audit flagged these features as `review_timing`, `requires_review`, and `medium` risk:

- `breadth_member_count`
- `breadth_thrust_10`
- `declining_share`
- `down_volume`
- `new_high_low_spread_5`
- `pct_above_ma20`
- `pct_above_ma50`
- `turnover_ma_60`
- `up_down_volume_ratio_5`
- `up_volume`

## Source And Timing Assumptions

Market breadth features are built in `build_market_breadth_from_csv` from the local OHLCV universe. The source rows are normalized to daily dates and aggregated by date. Breadth components such as advancers, decliners, percentage above moving average, new-high/new-low spread, and up/down volume are same-date market-universe aggregates.

Derived breadth features such as `breadth_thrust_10`, `new_high_low_spread_5`, and `up_down_volume_ratio_5` are rolling transformations of joined breadth columns. They are valid only if the joined breadth columns are available for the prediction date and are not filled from future dates.

`turnover_ma_60` is different. It is computed locally from the ticker OHLCV frame as a 60-day rolling mean of `close * volume`. It is not a joined market breadth feature. With the current implementation, it uses the current row and prior rows only.

## Date-Alignment Policy

The current context join behavior is:

- market proxy: exact normalized `date` join
- sector proxy: exact normalized `date` join after ticker-to-sector lookup
- market breadth: exact normalized `date` join
- foreign flow: exact normalized `ticker/date` join
- macro and cross-asset context: backward `merge_asof`, so a ticker row can use only the latest context row dated on or before the ticker date

Exact-date joins do not use future-dated context rows. If a context row is missing for a ticker date, the current market breadth block fills numeric breadth columns with `0.0`. This is conservative for tests because it avoids pulling a later context value backward, but it still deserves interpretation care: zero can mean missing context rather than a measured neutral breadth state.

## Forward-Fill Policy

The feature builder sorts rows by date before applying forward-fill. Forward-fill propagates earlier observed values to later rows. It must not backfill a later context value into an earlier prediction date.

For joined breadth and foreign-flow context, `apply_context_features` currently performs date joins without forward-filling the joined source values across missing dates. Macro context is the explicit exception: it uses backward as-of alignment by design, which is acceptable only for series whose release timing is compatible with the daily prediction date.

## Feature Type Distinctions

Local trailing OHLCV-derived features:

- built from the ticker's own OHLCV rows
- use rolling, lagged, or current-day transformations
- examples: `turnover_ma_60`, `turnover_ratio_20`, `amihud_20`, `volume_spike_zscore_20`

Joined market breadth features:

- built from the broader local OHLCV universe
- joined onto each ticker by normalized date
- examples: `breadth_member_count`, `declining_share`, `pct_above_ma20`, `pct_above_ma50`, `up_volume`, `down_volume`

External macro, foreign-flow, and context features:

- depend on separate artifacts or provider calls
- need release-date and source-timestamp validation
- examples: macro/cross-asset fields and `foreign_*` features

## Interpretation Of `review_timing`

`review_timing` means the feature is valid in principle but needs source-date, release-date, join, or forward-fill confirmation before being used for stronger claims. It does not prove leakage.

For market breadth, `review_timing` mainly reflects that the features are joined context aggregates and should have explicit same-date availability assumptions. For foreign-flow and macro features, it also reflects dependency on external artifacts or provider timing. For local trailing OHLCV features such as `turnover_ma_60`, timing review can be relaxed once tests confirm current-and-past-row behavior.

## Governance Rule Update

The governance review now distinguishes local OHLCV-derived flow features from joined context flow features:

- `turnover*`, `amihud*`, and `volume_spike*` style features are treated as local trailing features when their names and formulas indicate current/past-row computation.
- `foreign_*` and `abnormal_foreign*` features remain timing-review context features because they depend on joined foreign-flow inputs.

This reclassification does not change training behavior and does not remove any feature automatically.

## Remaining Limitations

- Same-day breadth availability still depends on when the full market universe data is assumed known relative to the prediction timestamp.
- Numeric zero after missing breadth joins can be ambiguous and should not be overinterpreted as a measured neutral breadth value.
- Live provider release timing was not validated in this task.
- The tests use synthetic data and validate mechanics, not market performance.
- These checks do not prove causality or trading performance.

## Recommended Next Validation

- Add explicit source-date metadata for breadth and foreign-flow artifacts where practical.
- Track missing-context indicators separately from measured zero values before changing feature-selection rules.
- Run a broader governance audit after timing metadata is available and compare whether timing-review flags decline for local trailing features only.
