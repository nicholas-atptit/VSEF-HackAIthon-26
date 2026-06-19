# VN30 Model Universe V6 Price/Return and Absolute-Direction Claim Boundary

- V6 is an offline diagnostic-only relock and confirmation audit for VN30 stock hourly forecasting.
- V6 uses V5 artifacts as inputs and does not run broad model search.
- Price/return relock freezes V5 survivor model family, target, horizon, and feature group; hyperparameters are selected on validation only; final is evaluated once.
- Absolute-direction confirmation is validation-governed under repaired metrics: raw accuracy, balanced accuracy, macro F1, MCC, AUC where available, prediction balance, and simple-baseline lift.
- feature_timestamp and target_timestamp split discipline is required for all rows.
- Final-ranked rows remain exploratory_not_claimable and cannot select claimable rows.
- No result is claimable now; future-blind-worthy candidates require a pre-registered future-blind test before stronger claims.
- Scope is VN30 stock hourly only; VN100 is out of scope.
- Index data may be used only as lagged market context or market-relative context; no index-as-stock claim is made.
- No trading, profitability, BUY/SELL, recommendation, investment advice, live deployment, daily T+1 system, production, DOCX, tag, merge, push --mirror, history rewrite, main-branch, or champion-replacement claim is made.
