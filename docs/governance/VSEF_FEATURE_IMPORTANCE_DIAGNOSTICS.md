# VSEF Feature Importance Diagnostics
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

This note documents the fold-level feature-importance diagnostics added for supported tree and boosting models in the walk-forward all-model evaluation path.

## Purpose

Feature-importance diagnostics provide a conservative governance view of which features are used by non-linear models across rolling walk-forward folds. They are intended to complement the existing Linear/Ridge/Lasso coefficient stability diagnostics.

The main questions are:

- which features repeatedly appear near the top of tree or boosting importance rankings
- whether non-linear feature importance is stable across rolling folds
- whether stable linear coefficient features are also stable in tree or boosting models
- whether feature governance should investigate unstable, model-specific, or method-specific signals

These diagnostics do not claim improved trading performance.

## Supported Models

The current extraction utility supports models that expose stable `feature_importances_` attributes through known wrapper surfaces:

- CART through the wrapped sklearn estimator
- XGBoost through the wrapped XGBoost sklearn estimator
- LightGBM through the wrapped LightGBM sklearn estimator
- Random Forest through the forecast sklearn estimator interface when that workflow supplies it

The current walk-forward all-model ML runner uses the `src.ml.models` registry. In that path, CART, XGBoost, and LightGBM can produce rows when they are included and successfully trained. Unsupported models are skipped without error.

## Output Files

The walk-forward all-model runner writes three additional CSV files under the existing run artifact directory:

- `csv/feature_importance_diagnostics.csv`
- `csv/feature_importance_stability_summary.csv`
- `csv/linear_vs_importance_feature_comparison.csv`

The follow-up feature governance review adds `csv/feature_governance_review.csv`, documented in `docs/governance/VSEF_FEATURE_GOVERNANCE_REVIEW.md`.

The integration point is `WalkForwardAllModelsStackingRunner`. This workflow treats each rolling prediction date as the effective fold and writes global CSV summaries under the existing `csv/` folder.

## Fold-Level Diagnostic Schema

`feature_importance_diagnostics.csv` contains one row per fold, model, horizon, task, and feature.

Columns:

- `fold_id`
- `step_size`
- `forecast_sequence_index`
- `ticker`
- `prediction_date`
- `model`
- `horizon`
- `task`
- `feature`
- `importance`
- `importance_rank`
- `importance_normalized`
- `train_start`
- `train_end`
- `eval_start`
- `eval_end`

Within each fold/model/horizon/task group, `importance_normalized` is scaled so positive importances sum to `1.0`. If the total importance is zero or unavailable, normalized importance is reported as `0.0`.

## Stability Summary Schema

`feature_importance_stability_summary.csv` aggregates fold-level importance rows by model, horizon, task, and feature.

Columns:

- `model`
- `horizon`
- `task`
- `feature`
- `fold_count`
- `mean_importance`
- `std_importance`
- `mean_importance_normalized`
- `std_importance_normalized`
- `mean_rank`
- `best_rank`
- `top_5_count`
- `top_10_count`
- `top_5_ratio`
- `top_10_ratio`
- `importance_stability_level`

The stability rule is intentionally simple:

- `high`: top-10 ratio is at least `0.8` and at least 3 folds are available
- `medium`: top-10 ratio is at least `0.5` and at least 3 folds are available
- `low`: otherwise

The top-10 ratio is the share of folds where a feature ranked in the top 10 for a given model/horizon/task group.

## Linear Comparison Schema

`linear_vs_importance_feature_comparison.csv` compares the existing linear coefficient stability summary with the feature-importance stability summary.

Columns:

- `horizon`
- `task`
- `feature`
- `linear_models_present`
- `linear_mean_abs_coefficient`
- `linear_best_sign_consistency_ratio`
- `linear_best_stability_level`
- `importance_models_present`
- `mean_importance_normalized`
- `best_top_10_ratio`
- `best_importance_stability_level`
- `alignment_label`

Alignment labels:

- `aligned_stable`: both linear stability and importance stability are `high` or `medium`
- `linear_only`: linear stability is `high` or `medium`, while importance stability is low or missing
- `importance_only`: importance stability is `high` or `medium`, while linear stability is low or missing
- `unstable_or_missing`: neither side is stable under the simple rule

## Interpretation

Stable feature importance can suggest that a feature is repeatedly useful to a tree or boosting model under the tested walk-forward setup. It does not prove the feature is causal, economically meaningful, or tradable.

Agreement between linear coefficient stability and non-linear importance stability is useful governance evidence. It can identify features worth reviewing more closely. Disagreement is also useful because it may reflect non-linear interactions, feature scaling, redundancy, regime sensitivity, or unstable training windows.

## Limitations

- These diagnostics do not prove trading performance.
- These diagnostics do not prove causality.
- Tree and boosting feature importance can be biased toward features with more split opportunities or stronger proxy relationships.
- Importances are model-specific and should not be compared as absolute magnitudes across unrelated algorithms without caution.
- Current outputs are based on the walk-forward all-model runner and its available algorithms.
- Random Forest support exists in the extraction utility through the forecast estimator interface, but Random Forest is not currently part of the `src.ml.models` all-model runner registry.

## Next Steps

- Add permutation-style diagnostics only after the current importance outputs are stable and tested.
- Compare stable importance features against regime-specific performance slices.
- Review highly ranked features for leakage risk, proxy effects, and redundant definitions.
- Keep feature-importance diagnostics as interpretability and governance outputs, not trading-performance evidence.
