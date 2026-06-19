# VSEF Feature Governance Review
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

This note documents the leakage-focused feature governance review added to the walk-forward all-model diagnostic workflow.

## Purpose

The feature governance review is a conservative, rule-based review layer for features that appear in linear coefficient stability diagnostics or tree/boosting feature-importance diagnostics.

It helps identify features that may need closer review because they are:

- highly ranked by tree or boosting models
- stable in linear diagnostics
- unstable across folds
- aliases or overlapping definitions
- external context features that require source-timestamp confirmation
- suspiciously close to target or future-return construction

The review does not remove features automatically and does not claim improved trading performance.

## Why Leakage Review Matters

Time-series forecasting can look better than it is if a feature contains information that would not have been available at the forecast timestamp. Leakage can come from obvious target columns, future-shifted values, delayed external data, overly broad forward fills, or redundant aliases that make model confidence look stronger than the underlying signal.

The review is intentionally cautious. A feature flagged for review is not necessarily invalid; it means the timing, source, or redundancy should be checked before using that feature to support stronger conclusions.

## Governance Categories

- `safe_trailing`: feature appears to be lagged, trailing, regime/risk, or current-day known data under transparent rules
- `requires_review`: feature is valid in principle but needs source timing, join, or availability confirmation
- `alias_or_redundant`: feature is a compatibility alias, legacy column, or overlapping definition
- `potential_leakage`: feature name suggests future, lead, lookahead, or price-reference information requiring proof
- `target_derived`: feature appears too close to target or forward-return construction
- `unknown`: insufficient registry metadata or name-rule evidence to classify safely

## Risk Levels

- `low`: no obvious leakage signal under the current rules
- `medium`: review needed because of source timing, redundancy, or fold instability
- `high`: feature should be excluded until timing or target independence is verified
- `unknown`: insufficient metadata to judge

## Output File

The walk-forward all-model runner writes:

- `csv/feature_governance_review.csv`

This file is written under the same `output_dir/csv/` folder as the existing diagnostics.

## Output Schema

`feature_governance_review.csv` contains one row per reviewed feature.

Columns:

- `feature`
- `governance_category`
- `risk_level`
- `reason`
- `source_hint`
- `is_context_feature`
- `is_regime_feature`
- `is_risk_feature`
- `is_alias_feature`
- `is_lagged_or_trailing`
- `appears_in_linear_stability`
- `appears_in_importance_stability`
- `best_linear_stability_level`
- `best_importance_stability_level`
- `best_top_10_ratio`
- `best_sign_consistency_ratio`
- `recommended_action`

## Recommended Actions

- `keep`: feature appears acceptable under the current rule-based review
- `keep_but_document`: feature appears structurally time-safe but diagnostics suggest instability or extra governance context
- `review_timing`: confirm release timing, join alignment, and forward-fill behavior
- `review_redundancy`: check whether the feature duplicates a canonical feature or backward-compatible alias
- `exclude_until_verified`: do not rely on the feature until timing and target independence are verified

## Limitations

- The review is rule-based and conservative.
- It does not prove leakage unless the implementation clearly uses future or target-period data.
- It does not prove causality.
- It does not prove trading performance.
- It does not replace manual inspection of source timestamps, joins, and feature formulas.
- It does not automatically delete or suppress features from model training.

## Next Steps

- Review high-risk and unknown features first.
- Confirm external context timing for macro, foreign-flow, breadth, market, and sector features.
- Review alias features and decide whether canonical names should be preferred in future governed feature sets.
- Compare review flags against regime-specific model performance without overclaiming causality.

## Follow-Up: Context Timing Governance

`docs/governance/VSEF_CONTEXT_TIMING_GOVERNANCE.md` documents the first targeted timing review for breadth and flow-style features. It clarifies that local `turnover*`, `amihud*`, and `volume_spike*` features are OHLCV-derived trailing features, while joined breadth, macro, and `foreign_*` features still require source-date timing review.

`docs/governance/VSEF_CONTEXT_AVAILABILITY_METADATA.md` documents the follow-up availability metadata for breadth and foreign-flow joins. Governance source hints now reference those support columns where relevant.

`docs/governance/VSEF_CONTEXT_COVERAGE_DIAGNOSTICS.md` documents fold-level missing-context coverage summaries that should be reviewed alongside timing-review flags.
