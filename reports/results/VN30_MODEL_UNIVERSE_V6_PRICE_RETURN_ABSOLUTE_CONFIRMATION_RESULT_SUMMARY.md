# VN30 Model Universe V6 Price/Return and Absolute-Direction Confirmation Result Summary

## Required Answers

1. V5 price/return candidates relocked: price__ridge__volatility_adjusted_return_h__h20__relative_strength, price__elasticnet__volatility_adjusted_return_h__h20__relative_strength, price__lasso__volatility_adjusted_return_h__h20__relative_strength, price__linear_regression__volatility_adjusted_return_h__h20__relative_strength.
2. Ridge volatility_adjusted_return_h h20 survived relock: no.
3. Did any price/return model robustly beat random walk / last price on final: no. Best validation-selected price row `v6_price_relock__lasso__volatility_adjusted_return_h__h20__relative_strength` final random-walk improvement -85.49 pp, final last-price improvement -85.49 pp.
4. Did any price/return model show usable sign accuracy or rank IC: yes. Best price row final sign accuracy 43.71%, final rank IC 0.0518.
5. Best absolute_direction candidate under repaired metrics: `v6_absolute__rbf_svm__absolute_direction__h40__market_context` with validation balanced accuracy 56.93%, macro F1 54.55%, MCC 0.1490.
6. Does any absolute_direction candidate beat the 61.61 champion on comparable scope: yes.
7. Candidates that remain future-blind worthy: 0 rows in `v6_candidate_decision.json`.
8. Is any result claimable: no.
9. Exact claim boundary: offline diagnostic-only VN30 stock hourly relock; validation-governed selection only; final rows are scoring-only and exploratory_not_claimable; no trading, profitability, BUY/SELL, recommendation, live deployment, daily T+1 system, VN100, index-as-stock, DOCX, tag, merge, push --mirror, main-branch, or champion-replacement claim is made.

## Decision Labels

- Price/return: `price_return_candidate_not_confirmed`.
- Absolute direction: `absolute_direction_candidate_not_confirmed`.
- Future blind: `not_claimable`.
- Claim: `not_claimable`.
