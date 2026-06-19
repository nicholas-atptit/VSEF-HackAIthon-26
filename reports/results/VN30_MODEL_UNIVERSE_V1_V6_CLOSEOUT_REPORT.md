# VN30 Model Universe V1-V6 Closeout Report

## Executive Summary

VN30 Model Universe V1-V6 is closed as an offline diagnostic benchmark audit. The work evaluated a broad direction and price/return model universe, promoted high-scoring exploratory rows into relock checks, enabled skipped families, repaired target and metric interpretation, and finished with a price/return plus absolute-direction confirmation pass.

The final closeout verdict is negative for replacement claims. V1-V6 did not produce a confirmed replacement for the existing 61.61% absolute-direction classical champion, The strongest apparent model-universe wins were explained by final-only discovery, market-relative class imbalance, seed instability, or failure to transfer after validation-governed relock.

## Timeline V1-V6

| Phase | Purpose | Main Evidence | Closeout Status |
|---|---|---|---|
| V1 broad benchmark | Evaluate direction and price/return targets across the model universe | 38 model families, 650 direction candidates, 650 price/return candidates. Best validation direction was `naive_bayes` absolute_direction h10, validation 66.00%, final 39.86%. | Diagnostic only; no replacement. |
| V2 promotion relock | Recheck high final exploratory rows by validation-governed relock | Absolute h40 rows reached 69.86%-70.29% final in exploratory or relock context, but final-discovered families required future-blind confirmation. | No promotable replacement. |
| V3 skipped families | Enable statistical, deep sequence, and ensemble families | BiLSTM market_relative_vn30 h40 reached validation 64.06%, final 72.50%, labeled future_blind_required. | Promising diagnostic, not claimable. |
| V4 BiLSTM relock | Reconstruct and stress test the BiLSTM candidate | Split audit passed, but same-target always-down baseline reached final 79.69%; seed final accuracy std was 0.0797. | Demotion pressure from baseline and seed instability. |
| V5 target/metric repair | Repair class imbalance and metric interpretation | BiLSTM final balanced accuracy 47.78%, macro F1 46.08%, MCC -0.0603, final predicted-positive ratio 9.69%, majority baseline 79.69%. | BiLSTM demoted; best repaired target is absolute_direction. |
| V6 relock and confirmation | Relock V5 price/return survivors and confirm absolute_direction under repaired metrics | Price rows did not survive final relock. Absolute-direction decision was not confirmed. Future-blind registry after V6 is empty. | No claimable result. |

## Model Families Evaluated

V1 evaluated 38 model families and 1,300 total candidates across direction and price/return tasks. The evaluated universe included simple direction baselines, logistic and calibrated logistic models, linear and RBF SVMs, KNN, Naive Bayes, random forest, extra trees, gradient boosting, histogram gradient boosting, XGBoost, LightGBM, MLP, random-walk and return baselines, linear regression, ridge, lasso, elastic net, SVR, tree regressors, and neural-network regressors.

V3 extended coverage to statistical, deep sequence, ensemble, and non-MVP diagnostics. Statistical and deep/sequence families produced validation improvements in some settings, but validation-to-final transfer and repaired metrics did not support a replacement claim.

## Direction Forecasting Findings

The broad direction benchmark found validation signal, but it did not survive the full claim path. V1 selected `direction__naive_bayes__absolute_direction__h10__relative_strength` by validation accuracy, but final accuracy fell to 39.86%. V2 found stronger h40 absolute-direction final rows, including 69.86% and 70.29% final accuracy in exploratory or relock contexts, but those rows were tied to final-discovered hypothesis families and stayed future-blind-required or exploratory_not_claimable.

V5 identified absolute_direction as the least class-imbalance-contaminated repaired target. V6 then tested absolute_direction h20, h40, and h60 under repaired metrics. The best validation repaired row was `v6_absolute__rbf_svm__absolute_direction__h40__market_context`, with validation balanced accuracy 56.93%, macro F1 54.55%, and MCC 0.1490, but it did not confirm on final. Some h40 rows exceeded the 61.61% raw final accuracy context, but they remain exploratory_not_claimable and cannot replace the champion.

## Market-Relative Target Failure Modes

Market-relative rows created the largest apparent final accuracies but also the clearest failure mode. The market_relative_vn30 h40 BiLSTM reached 72.50% final raw accuracy, but the final split was dominated by one class. The same-target always-down baseline reached 79.69% final accuracy, and the BiLSTM final predicted-positive ratio was only 9.69%.

V5 repaired metrics showed that the BiLSTM raw final accuracy did not represent balanced directional skill: final balanced accuracy was 47.78%, macro F1 was 46.08%, and MCC was -0.0603. This demotes the market-relative BiLSTM row from a future-blind candidate to negative evidence about target imbalance and baseline fragility.

## BiLSTM Relock and Demotion

The BiLSTM market_relative_vn30 h40 candidate was reconstructed in V4 with split/leakage audit pass. That removed one concern but exposed two stronger problems: seed instability and class-balance sensitivity. Seed final accuracy had std 0.0797, and the same-target always-down baseline beat the BiLSTM on final.

V5 completed the demotion. The BiLSTM's 72.50% raw final result was mostly class-imbalance driven, because the final majority baseline was 79.69% and repaired final metrics were weak. The row is not a replacement for the 61.61% absolute-direction champion, not a live or trading result.

## Price/Return Forecasting Findings

V1 and V3 found validation-screened price/return rows with positive baseline improvements, and V5 identified four robust-looking V5 survivors: ridge, elastic net, lasso, and linear regression on volatility_adjusted_return_h h20 with relative_strength features. V6 froze each survivor's model family, target, horizon, and feature group, selected hyperparameters by validation only, and evaluated final once.

The V6 relock did not confirm price/return forecasting. The best validation-selected V6 price row was `v6_price_relock__lasso__volatility_adjusted_return_h__h20__relative_strength`, but its final improvement was -85.49 pp versus random walk and -85.49 pp versus last price. It had final sign accuracy 43.71% and final rank IC 0.0518, which is not enough for a robust claim.

## Why No V1-V6 Result Becomes Claimable

No V1-V6 row satisfies the full claim path:

- V1 broad winners did not transfer cleanly from validation to final.
- V2 high final rows were final-discovered and require future-blind confirmation.
- V3 BiLSTM market-relative performance was diagnostic only and target-specific.
- V4 showed split audit pass but seed instability and a stronger same-target trivial baseline.
- V5 repaired metrics demoted the BiLSTM and found no repaired champion replacement.
- V6 relock did not confirm V5 price/return survivors or absolute-direction candidates.
- The V6 future-blind registry is empty.

Final-ranked rows remain exploratory_not_claimable. No result may be selected as claimable by final performance.

## Remaining Valid Claims

- The existing 61.61% absolute-direction classical champion remains separate and is not replaced by the model-universe run.
- QML is excluded from the HackAIthon MVP scope.
- The model universe produced useful negative evidence and benchmark audit artifacts, but no confirmed replacement.

## Recommended Next Steps

1. Freeze model-universe tuning for this branch.
2. Use V1-V6 findings as negative evidence and benchmark audit material.
3. Revisit only with new data, a pre-registered future-blind ledger, or a redesigned target.
4. Keep direction metrics separate from price/return metrics.
5. QML is excluded from the HackAIthon MVP scope.

## Exact Claim Boundary

This closeout is offline diagnostic-only and scoped to VN30 stock hourly forecasting. It makes no trading, profitability, BUY/SELL, recommendation, investment advice, live deployment, daily T+1 system, production, VN100, index-as-stock, DOCX, tag, merge, push --mirror, main-branch, or champion-replacement claim. V1-V6 results are benchmark audit evidence only. Future stronger claims require a pre-registered future-blind evaluation with unchanged target, split, features, metrics, and model selection rules.

