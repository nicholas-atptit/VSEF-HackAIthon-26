# Active Evidence Index

- Created at UTC: 2026-05-17.
- Branch: `research/vn100-evidence-hardening-v1`.
- Purpose: identify the current evidence tracks and their claim boundaries after repository cleanup.

## 1. Stock Hourly Available-Window

Current status:

- Actual stock hourly coverage starts in 2023.
- Canonical evaluator has a baseline60 result.
- Final65 overall directional performance is not established.
- This track must not be described as 2015-2022 stock hourly evidence.

Active reports:

- `reports/results/VN30_HOURLY_DATA_FORENSICS_DIAGNOSIS.md`
- `reports/results/VN30_HOURLY_2015_BASELINE60_RESULT_LOCK.md`
- `reports/claims/VN30_HOURLY_2015_BENCHMARK_CLAIM_REGISTER.md`
- `reports/protocols/VN30_HOURLY_2015_CANONICAL_EVALUATOR_DECISION.md`
- `reports/protocols/VN30_HOURLY_2015_VALIDATION_FINAL_MISMATCH_PROTOCOL.md`
- `reports/results/VN30_HOURLY_SELECTED_CANDIDATE_ARTIFACT_DISCOVERY.md`
- `reports/protocols/VN30_HOURLY_SELECTED_CANDIDATE_ROW_LEVEL_RERUN_PROTOCOL.md`
- `reports/results/VN30_HOURLY_SELECTED_CANDIDATE_ROLLING_STABILITY_RESULT.md`
- `reports/claims/VN30_HOURLY_SELECTED_CANDIDATE_CLAIM_BOUNDARY.md`
- `reports/results/VN30_HOURLY_SELECTED_CANDIDATE_STABILITY_AUDIT_RESULT.md`
- `reports/claims/VN30_RESEARCH_CLAIM_REGISTER.md`

Active scripts:

- `scripts/research/vn30_hourly_2015_canonical_eval.py`
- `scripts/research/vn30_hourly_available_window_common.py`
- `scripts/research/run_vn30_hourly_available_window_benchmark.py`
- `scripts/research/audit_vn30_hourly_available_window.py`
- `scripts/research/rerun_vn30_hourly_selected_candidate_row_predictions.py`
- `scripts/research/audit_vn30_hourly_selected_candidate_rolling_stability.py`
- `scripts/research/audit_vn30_hourly_selected_candidate_stability_summary.py`
- `scripts/research/run_vn30_hourly_available_window_confidence_sweep.py`
- `scripts/research/run_vn30_hourly_available_window_exante_regime_validation.py`
- `scripts/research/run_vn30_hourly_available_window_cost_slippage_validation.py`

Generated summary directories:

- `reports/generated/vn30_hourly_available_window/`
- `reports/generated/vn30_hourly_data_forensics/`
- `reports/generated/vn30_hourly_selected_candidate_rolling/`

Claim boundary:

- May report only available-window stock hourly results with exact scope, dates, ticker universe, evaluator, baseline, horizon, and final accuracy.
- Must not claim final65 overall directional success.
- Must not claim 2015-2022 stock hourly data exists locally.

## 2. Stock Daily 2015

Current status:

- 30/30 VN30 tickers are usable after BCM/VIB recovery.
- Best daily result remains below 60%.
- Daily tuning stopped after postmortem.

Active reports:

- `reports/protocols/VN30_DAILY_2015_SCOPE_AND_DESIGN.md`
- `reports/results/VN30_DAILY_2015_BCM_VIB_RECOVERY_REPORT.md`
- `reports/results/VN30_DAILY_2015_RESULT_SUMMARY.md`
- `reports/claims/VN30_DAILY_2015_CLAIM_REGISTER.md`
- `reports/protocols/VN30_DAILY_2015_TARGET60_FAILURE_POSTMORTEM_PROTOCOL.md`
- `reports/protocols/VN30_DAILY_2015_TARGET60_NEXT_STEP_DECISION.md`
- `reports/results/VN30_DAILY_2015_TARGET60_RESULT_SUMMARY.md`
- `reports/results/VN30_DAILY_2015_TARGET60_V2_RESULT_SUMMARY.md`

Active scripts:

- `scripts/research/fetch_vn30_daily_gateway_2015.py`
- `scripts/research/validate_vn30_daily_2015.py`
- `scripts/research/run_vn30_daily_2015_benchmark.py`
- `scripts/research/audit_vn30_daily_2015_benchmark.py`
- `scripts/research/run_vn30_daily_2015_target60_optimization.py`
- `scripts/research/audit_vn30_daily_2015_target60_failure_postmortem.py`
- `scripts/research/run_vn30_daily_2015_target60_v2.py`
- `scripts/research/audit_vn30_daily_2015_target60_v2.py`

Generated summary directories:

- `reports/generated/vn30_daily_2015/`
- `reports/generated/vn30_daily_2015_target60/`
- `reports/generated/vn30_daily_2015_target60_postmortem/`
- `reports/generated/vn30_daily_2015_target60_v2/`

Claim boundary:

- May report stock daily 2015 results only with exact benchmark scope and baselines.
- Must not present daily results as hourly results.
- Must not claim 60% daily directional accuracy was reached.

## 3. Index Directional Benchmark

Current status:

- Daily and hourly index-only benchmark exists.
- Index claims are separate from stock claims.
- Hourly index results use actual available hourly cache rows starting in 2022, not synthetic or resampled 2015 hourly data.

Active reports:

- `reports/results/VN30_INDEX_BENCHMARK_RESULT_SUMMARY.md`
- `reports/claims/VN30_INDEX_BENCHMARK_CLAIM_REGISTER.md`
- `reports/protocols/INDEX_HOURLY_FETCH_README.md`

Active scripts:

- `scripts/research/index_benchmark_common.py`
- `scripts/research/fetch_supported_indices_daily_gateway_2015.py`
- `scripts/research/fetch_supported_indices_hourly_gateway_2015.py`
- `scripts/research/fetch_vnstock_supported_indices_hourly.py`
- `scripts/research/validate_supported_indices_benchmark_readiness.py`
- `scripts/research/validate_supported_indices_hourly_gateway.py`
- `scripts/research/validate_supported_indices_hourly_gateway_2015.py`
- `scripts/research/run_supported_indices_directional_benchmark.py`
- `scripts/research/audit_supported_indices_data_scope.py`
- `scripts/research/audit_supported_indices_directional_benchmark.py`

Generated summary directories:

- `reports/generated/index_benchmark/`
- `reports/generated/index_hourly_fetch/`
- `reports/generated/index_hourly_gateway/`
- `outputs/index_directional_benchmark/` local ignored output directory

Claim boundary:

- May report only exact index, frequency, model, horizon, final accuracy, row count, and baseline comparison.
- Must not support stock benchmark claims.
- Must not present daily index results as hourly results.
- Must not present available hourly cache results as 2015 hourly results.

## 4. VN30 Hourly Paper Source Artifacts

Current status:

- Paper-source tables, figures, and TODO indexes are named with explicit VN30 hourly scope.
- Builders must read existing artifacts only and must not fetch data, train models, run broad benchmarks, or generate DOCX/paper content during cleanup.

Active reports:

- `reports/paper/VN30_HOURLY_PAPER_FIGURE_DATA_SOURCE_INVENTORY.md`
- `reports/paper/VN30_HOURLY_PAPER_TABLE_FIGURE_CAPTIONS_EN.md`
- `reports/paper/VN30_HOURLY_PAPER_TABLE_FIGURE_CAPTIONS_VI.md`
- `reports/paper/VN30_HOURLY_PAPER_MISSING_METRICS_TODO.md`
- `reports/paper/VN30_HOURLY_PAPER_ROW_LEVEL_FIGURE_TODO.md`
- `reports/paper/VN30_HOURLY_PAPER_LITERATURE_DATA_TODO.md`

Active scripts:

- `scripts/research/build_vn30_hourly_paper_empirical_tables.py`
- `scripts/research/build_vn30_hourly_paper_empirical_figures.py`

Generated summary directories:

- `reports/generated/paper_tables_current/`
- `reports/generated/paper_figures_current/`

Claim boundary:

- These files define source/caption/TODO artifacts only.
- They do not create new empirical results, paper drafts, DOCX files, or trading/profitability claims.

## 5. Data Forensics

Current status:

- No stock hourly 2015-2022 data exists locally.
- Data was not deleted by cleanup.
- Raw, cache, output, and archive snapshot locations remain protected by `.gitignore` and cleanup policy.

Active reports:

- `reports/results/VN30_HOURLY_DATA_FORENSICS_DIAGNOSIS.md`
- `reports/results/VNSTOCK_DATA_REPO_SOURCE_INVESTIGATION.md`
- `reports/protocols/VNSTOCK_AGENT_DATA_GUIDE.md`
- `reports/protocols/VNSTOCK_AGENT_DATA_GUIDE_SUMMARY.md`

Active scripts:

- `scripts/research/audit_vn30_hourly_data_locations.py`
- `scripts/research/verify_vnstock_data_environment.py`
- `scripts/research/verify_repo_vnstock_provider_paths.py`
- `scripts/research/audit_vn30_hourly_coverage_2005_2026.py`

Generated summary directories:

- `reports/generated/vn30_hourly_data_forensics/`
- `reports/generated/environment/`

Claim boundary:

- May report local coverage and repository tracking status.
- Must not imply missing data was available or deleted.
- Must not fetch replacement data as part of cleanup.

## 6. Top-k Ranking

Current status:

- Separate metric family from overall directional accuracy.
- Not used for overall directional claims.

Active reports:

- `reports/results/VN30_HOURLY_2015_TOPK_RANKING_RESULT_SUMMARY.md`
- `reports/protocols/VN30_HOURLY_2015_TOPK_RANKING_PROTOCOL.md`
- `reports/claims/VN30_HOURLY_2015_TOPK_RANKING_CLAIM_REGISTER.md`
- `reports/protocols/VN30_HOURLY_2015_TOPK_75_VERIFICATION_DECISION.md`
- `reports/protocols/VN30_HOURLY_2015_TOPK_75_VERIFICATION_PROTOCOL.md`

Active scripts:

- `scripts/research/run_vn30_hourly_2015_topk_ranking_experiments.py`
- `scripts/research/audit_vn30_hourly_2015_topk_ranking_results.py`
- `scripts/research/verify_vn30_hourly_2015_topk_75_result.py`
- `scripts/research/verify_vn30_hourly_2015_topk_75_null_test.py`

Generated summary directories:

- `reports/generated/vn30_hourly_2015_topk_verification/`

Claim boundary:

- May discuss only top-k ranking metrics with their exact protocol.
- Must not translate top-k ranking results into overall directional accuracy.
