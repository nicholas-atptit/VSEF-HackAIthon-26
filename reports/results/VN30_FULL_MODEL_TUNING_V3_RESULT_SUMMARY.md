# VN30 Full Model Tuning V3 Result Summary

## Baselines

- Current claimable champion: L2 Logistic, feature_set_C_closest, h40, threshold 0.50, 61.61% final accuracy, +10.90 pp lift, 4,074 rows.
- Current exploratory best: Logistic Regression, compact_stable_features, h50, threshold 0.525, 64.76% final accuracy, +11.18 pp lift, 3,774 rows.

## Best Validation-Governed Candidate

- Candidate: `v3grid_000001__t0p450`.
- Model family: logistic_regression.
- Target variant: absolute_direction.
- Feature group: compact_stable_features.
- Horizon/threshold: h20 / 0.45.
- Validation accuracy/lift: 50.10% / +0.02 pp.
- Final accuracy/lift: 52.12% / +0.00 pp.
- Claim label: not_claimable.

## Best Exploratory Final Candidate

- Candidate: `forced_v3_calibrated_compact_h40__t0p540`.
- Model family: calibrated_logistic.
- Target variant: absolute_direction.
- Feature group: compact_stable_features.
- Horizon/threshold: h40 / 0.54.
- Final accuracy/lift: 65.51% / +14.80 pp.
- Claim label: exploratory_not_claimable.

## Required Answers

1. Did any validation-governed candidate beat 61.61%: false.
2. Did any validation-governed candidate beat +10.90 pp lift: false.
3. Did any exploratory candidate beat 64.76%: true.
4. Did any exploratory candidate beat +11.18 pp lift: true.
5. Best target variant by final-ranked evidence: absolute_direction.
6. Best feature group by final-ranked evidence: compact_stable_features.
7. Best model family by final-ranked evidence: calibrated_logistic.
8. Promotion/future-blind candidates: forced_v3_calibrated_compact_h40__t0p540, forced_v3_calibrated_compact_h40__t0p545, forced_v3_calibrated_all_stable_h35__t0p630, forced_v3_calibrated_compact_h40__t0p535, forced_v3_calibrated_all_stable_h35__t0p625, forced_v3_calibrated_all_stable_h40__t0p650, forced_v3_calibrated_all_stable_h35__t0p635, forced_v3_calibrated_all_stable_h40__t0p645, forced_v3_calibrated_all_stable_h40__t0p640, forced_v3_calibrated_all_stable_h40__t0p630.
9. Result that remains claimable: current 61.61% L2 Logistic baseline60_candidate remains claimable.
10. Baseline60 defensible: false; target62 defensible: false; final65 defensible: false.

Paper-safe wording:

> VN30 Full Model Tuning v3 evaluated lagged market-index context features, multiple target variants, and staged model-family screening under strict target_timestamp split discipline. The current 61.61% strict-replay L2 Logistic absolute-direction champion is not replaced by this run. Final-ranked candidates outside validation governance are exploratory only and require re-lock or future-blind confirmation before any claim.
