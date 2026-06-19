# Model Universe Claim Boundary

## Claim Boundary for Paper Interpretation

- The fixed current h40 paper result remains Logistic L2 / baseline_C_closest / h40 / validation-selected threshold 0.55 / final accuracy 61.63% / full 30-stock coverage.
- The bull_bear_sideway_router h40 fixed 0.50 final accuracy 63.33% row is descriptive final-window context only and is not claim-eligible.
- The soft-voting final accuracy 62.00% cooperation row is descriptive context only and is not claim-eligible.
- Rows with high validation and poor final transfer, including stacking_xgboost_meta diagnostics, are interpreted as validation-final transfer or overfit failures rather than as main results.
- KNN-support rows are diagnostic support experiments and do not replace the main claim.
- GARCH is a volatility diagnostic only and not a direct headline direction classifier.
- Market-index evidence is market-context evidence and cannot substitute for stock-level VN30 evidence.
- No ticker subset, confidence abstention, or top-k/ranking substitute is used for headline accuracy.
- No trading readiness, profitability, investment advice, final65, live deployment, or generalization beyond the reported VN30 evidence is claimed.

## Run Audit Context

- Final-window scores are scoring-only and are not used for model, feature, threshold, horizon, ensemble, calibration, or router selection.
- The current h40 paper result remains Logistic L2 / baseline_C_closest / h40 / validation-selected threshold 0.55 / 61.63% unless a new model is validation-selected, full-coverage, and audit-passed.
- GARCH is diagnostic only and not a direct headline direction classifier.
- Total planned/run/failed/skipped/not recommended: 75/74/0/0/1.
- CatBoost status: run.
- GARCH diagnostic status: not_recommended_with_reason.
- No trading, profitability, investment recommendation, or live-deployment claim is made.

| candidate_id | model_id | validation_accuracy | final_accuracy | beats_61_63_yes_no | claim_eligible_yes_no | reason_not_claim_eligible | overfit_risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| universe__ensemble_stacking__stacking_xgboost_meta__validation_selected_base_models__h80__validation_selected_threshold__t0p525 | stacking_xgboost_meta | 0.6724941724941725 | 0.4968684759916493 | no | no | selected but high validation-final gap / poor final transfer / high overfit risk | high |
