# VSEF Linear Fold Diagnostics
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

This note documents the fold-level coefficient diagnostics added for Linear Regression, Ridge, and Lasso in the walk-forward all-model evaluation path.

## Purpose

Linear/Ridge/Lasso models are kept as interpretable shadow or baseline-style models. Their main value in this repository is not to claim superior forecasting performance, but to provide a simple diagnostic view of how governed features behave across rolling train/evaluation windows.

The fold-level coefficient diagnostics help answer conservative research questions:

- which features receive nonzero linear weight across folds
- whether coefficient signs are stable or unstable across rolling windows
- whether feature directionality changes materially over time
- whether linear baselines are useful as feature sanity checks before relying on more complex models

## Output Files

The walk-forward all-model runner writes two additional CSV files under the existing run artifact directory:

- `csv/linear_coefficient_diagnostics.csv`
- `csv/linear_coefficient_stability_summary.csv`

The follow-up feature-importance diagnostics add non-linear comparison outputs documented in `docs/governance/VSEF_FEATURE_IMPORTANCE_DIAGNOSTICS.md`.

The current integration point is `WalkForwardAllModelsStackingRunner`. This workflow does not maintain a separate per-fold directory; each rolling prediction date is treated as the effective fold and the coefficient rows are written to the global `csv/` directory.

## Fold-Level Diagnostic Schema

`linear_coefficient_diagnostics.csv` contains one row per fold, model, horizon, task, and feature.

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
- `coefficient`
- `coefficient_sign`
- `coefficient_magnitude`
- `intercept`
- `nonzero_coefficient_count`
- `feature_count`
- `train_start`
- `train_end`
- `eval_start`
- `eval_end`

The current task is `return`, because the implemented Linear/Ridge/Lasso forecast models are regression models.

## Stability Summary Schema

`linear_coefficient_stability_summary.csv` aggregates fold-level coefficient rows by model, horizon, task, and feature.

Columns:

- `model`
- `horizon`
- `task`
- `feature`
- `fold_count`
- `mean_coefficient`
- `std_coefficient`
- `mean_abs_coefficient`
- `sign_positive_count`
- `sign_negative_count`
- `sign_zero_count`
- `sign_consistency_ratio`
- `coefficient_cv`
- `stability_level`

## Stability Rule

The stability rule is intentionally simple:

- `high`: sign consistency ratio is at least `0.8` and at least 3 folds are available
- `medium`: sign consistency ratio is at least `0.6` and at least 3 folds are available
- `low`: otherwise

The sign consistency ratio is the largest sign count divided by the number of folds for that model/horizon/task/feature group.

## Interpretation

Stable coefficient signs may indicate that a feature has a consistent linear association with the target inside the tested walk-forward windows. This should be treated as interpretability evidence, not causal evidence.

Unstable signs may indicate regime sensitivity, feature redundancy, scaling issues, changing market structure, or insufficient fold support. A low stability label is not proof that a feature is useless; it means the linear association was not stable under this diagnostic rule.

Coefficient magnitude should be interpreted with care because feature scales differ. Magnitudes are most useful after checking feature scaling, feature definition, and fold coverage.

## Limitations

- These diagnostics do not prove trading performance.
- These diagnostics do not prove causality.
- Linear/Ridge/Lasso remain shadow or interpretable baseline models, not research-core or decision-core models.
- The output uses rolling folds from the walk-forward all-model runner, not a separate model-selection proof.
- Current fold stability covers return regression only.
- Stability labels depend on fold count and feature availability.

## Next Steps

- Use the feature-importance comparison output to review agreement and disagreement with CART, XGBoost, and LightGBM importance stability.
- Consider permutation diagnostics only after the current coefficient and feature-importance outputs are stable.
- Add fold-level diagnostics to other walk-forward workflows only if their artifact structure has a clear insertion point.
- Consider scale-normalized coefficient reporting if feature standardization is introduced.
- Track whether coefficient instability lines up with detected market regimes, without overclaiming causality.
