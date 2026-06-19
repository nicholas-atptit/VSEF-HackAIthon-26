# Usage Guide
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Workflow guide |
| Created / authored | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `8800ce6e3780c7978856737e70cb5e3b999eacee` |
| Timestamp source | current metadata standardization run |
| Status | Active |

This guide documents the runnable ML and evaluation workflows that currently exist in the repository.

All commands below are intended to be run from the repository root.

## Prerequisites

1. Install Python dependencies.

```bash
pip install -r requirements.txt
```

2. Ensure `vnstock` can fetch data in your environment.

3. Optional model dependencies are not mandatory:

- `sarimax` and `ets` require `statsmodels`
- `xgboost` requires `xgboost`
- `lightgbm` requires `lightgbm`
- sequence models require the relevant deep-learning stack if you choose them

If an optional family is unavailable, the comparison workflows skip it and record the reason in `run_config.json` or the printed CLI summary.

## Common Defaults

Most recent research workflows use the same ticker set and default split:

- tickers: `DGC ACB MWG HPG`
- train start: `2020-01-01`
- train end: `2025-12-31`
- eval start: `2026-01-01`
- eval end: `2026-04-10`

Forward-return and dual-task workflows evaluate the requested window on realized `target_date`.

## Workflow Dependency Chain

- `run_backtest_real_data.py` is standalone.
- `run_backtest_model_comparison.py` is standalone.
- `run_backtest_forward_return.py` is standalone.
- `run_strategy_backtest.py` reads forward-return artifacts and can rerun them if missing.
- `run_dual_task_backtest.py` is standalone.
- `run_combined_signal_analysis.py` requires `artifacts/dual_task/`.
- `run_regime_aware_analysis.py` requires `artifacts/dual_task/` and `artifacts/combined_signal/`.
- `run_walk_forward_regime_robustness.py` orchestrates repeated fold runs internally.
- `run_meta_selector.py` requires `artifacts/walk_forward_regime_robustness/`.
- `run_context_meta_selector.py` requires both `artifacts/walk_forward_regime_robustness/` and `artifacts/meta_selector/`.

## 1. Fixed-Window Real-Data Backtest

Purpose:

- Train a single close-level forecasting path on a fixed window of real vnstock data.
- Compare it against a naive previous-close baseline.

Command:

```bash
python scripts/run_backtest_real_data.py --tickers DGC ACB MWG HPG --train-start 2020-01-01 --train-end 2025-12-31 --eval-start 2026-01-01 --eval-end 2026-04-10 --output-dir artifacts/backtest
```

Important arguments:

- `--algorithms cart`
- `--primary-algorithm cart`
- tree and sequence hyperparameters if needed

Main outputs:

- `artifacts/backtest/predicted_vs_actual.csv`
- `artifacts/backtest/metrics_summary.csv`
- `artifacts/backtest/fetch_summary.csv`
- `artifacts/backtest/training_summary.csv`
- `artifacts/backtest/run_config.json`
- `artifacts/backtest/charts/`
- `artifacts/backtest/models/`

## 2. Fixed-Window Model Comparison

Purpose:

- Compare multiple model families on the same fixed-window real-data close-level backtest.

Command:

```bash
python scripts/run_backtest_model_comparison.py --tickers DGC ACB MWG HPG --train-start 2020-01-01 --train-end 2025-12-31 --eval-start 2026-01-01 --eval-end 2026-04-10 --algorithms cart,xgboost,lightgbm,sarimax,ets --output-dir artifacts/backtest_model_comparison
```

Main outputs:

- `artifacts/backtest_model_comparison/predicted_vs_actual.csv`
- `artifacts/backtest_model_comparison/model_comparison.csv`
- `artifacts/backtest_model_comparison/overall_model_ranking.csv`
- `artifacts/backtest_model_comparison/fetch_summary.csv`
- `artifacts/backtest_model_comparison/training_summary.csv`
- `artifacts/backtest_model_comparison/run_config.json`

## 3. Forward-Return Backtest

Purpose:

- Forecast trading-day forward returns for `3d`, `5d`, and `20d`.

Command:

```bash
python scripts/run_backtest_forward_return.py --tickers DGC ACB MWG HPG --train-start 2020-01-01 --train-end 2025-12-31 --eval-start 2026-01-01 --eval-end 2026-04-10 --horizons 3d,5d,20d --algorithms cart,xgboost,lightgbm,sarimax,ets --output-dir artifacts/backtest_forward_return
```

Optional flags:

- `--disable-momentum-baseline`

Main outputs:

- `artifacts/backtest_forward_return/3d/`
- `artifacts/backtest_forward_return/5d/`
- `artifacts/backtest_forward_return/20d/`
- `artifacts/backtest_forward_return/overall_horizon_summary.csv`
- `artifacts/backtest_forward_return/overall_horizon_ranking.csv`

Each horizon folder contains:

- `predicted_vs_actual.csv`
- `metrics_summary.csv`
- `model_comparison.csv`
- `overall_model_ranking.csv`
- `fetch_summary.csv`
- `training_summary.csv`
- `run_config.json`
- `charts/`

## 4. Strategy Backtest Layer

Purpose:

- Convert saved forward-return forecasts into analysis-only long-only threshold strategies with costs and slippage.

Command:

```bash
python scripts/run_strategy_backtest.py --tickers DGC ACB MWG HPG --train-start 2020-01-01 --train-end 2025-12-31 --eval-start 2026-01-01 --eval-end 2026-04-10 --forecast-output-dir artifacts/backtest_forward_return --output-dir artifacts/strategy_backtest
```

Optional flags:

- `--thresholds 0.0,0.005,0.01,0.02`
- `--transaction-fee-bps 15`
- `--slippage-bps 20`
- `--disable-momentum-baseline`
- `--disable-forecast-rerun`

Main outputs:

- `artifacts/strategy_backtest/3d/`
- `artifacts/strategy_backtest/5d/`
- `artifacts/strategy_backtest/20d/`
- `artifacts/strategy_backtest/summary/overall_strategy_ranking.csv`
- `artifacts/strategy_backtest/summary/model_horizon_threshold_summary.csv`
- `artifacts/strategy_backtest/charts/`

Each horizon folder contains:

- `trades.csv`
- `strategy_metrics.csv`
- `equity_curve.csv`
- `portfolio_metrics.csv`
- `fetch_summary.csv`
- `run_config.json`

## 5. Dual-Task Backtest

Purpose:

- Train and evaluate both:
  - regression for forward return
  - classification for profit/loss after costs

Command:

```bash
python scripts/run_dual_task_backtest.py --tickers DGC ACB MWG HPG --train-start 2020-01-01 --train-end 2025-12-31 --eval-start 2026-01-01 --eval-end 2026-04-10 --horizons 3d,5d,20d --algorithms cart,xgboost,lightgbm,sarimax,ets --transaction-fee-bps 15 --slippage-bps 20 --output-dir artifacts/dual_task
```

Main outputs:

- `artifacts/dual_task/regression/{3d,5d,20d}/`
- `artifacts/dual_task/classification/{3d,5d,20d}/`
- `artifacts/dual_task/models/`
- `artifacts/dual_task/summary/dual_task_summary.csv`
- `artifacts/dual_task/summary/cross_task_model_ranking.csv`
- `artifacts/dual_task/summary/joined_regression_classification_evaluation.csv`

## 6. Combined-Signal Analysis

Purpose:

- Merge `predicted_return` and `predicted_profit_probability` into combined research signals.

Command:

```bash
python scripts/run_combined_signal_analysis.py --dual-task-dir artifacts/dual_task --output-dir artifacts/combined_signal --horizons 3d,5d,20d --return-thresholds 0.0,0.005,0.01,0.02 --probability-thresholds 0.50,0.55,0.60,0.65 --w-return 0.5 --w-profit 0.5 --top-k-values 1,3,5
```

Optional flag:

- `--ranking-group date`
- `--ranking-group week`

Main outputs:

- `artifacts/combined_signal/{3d,5d,20d}/combined_signal_table.csv`
- `artifacts/combined_signal/{3d,5d,20d}/combined_bucket_summary.csv`
- `artifacts/combined_signal/{3d,5d,20d}/combined_ranking_summary.csv`
- `artifacts/combined_signal/{3d,5d,20d}/probability_calibration_summary.csv`
- `artifacts/combined_signal/summary/overall_combined_signal_summary.csv`
- `artifacts/combined_signal/summary/cross_horizon_combined_ranking.csv`

## 7. Regime-Aware Analysis

Purpose:

- Slice regression, classification, and combined-signal performance by `bull`, `bear`, and `sideway`.

Command:

```bash
python scripts/run_regime_aware_analysis.py --dual-task-dir artifacts/dual_task --combined-signal-dir artifacts/combined_signal --output-dir artifacts/regime_aware_analysis --benchmark-symbol VNINDEX --benchmark-source vnindex_or_market_proxy --regime-lookback-days 20 --bull-threshold 0.03 --bear-threshold -0.03
```

Main outputs:

- `artifacts/regime_aware_analysis/3d/`
- `artifacts/regime_aware_analysis/5d/`
- `artifacts/regime_aware_analysis/20d/`
- `artifacts/regime_aware_analysis/summary/overall_regime_summary.csv`
- `artifacts/regime_aware_analysis/summary/regime_model_horizon_ranking.csv`
- `artifacts/regime_aware_analysis/summary/regime_combined_method_ranking.csv`

Each horizon folder contains:

- `regime_labeled_signal_table.csv`
- `regression_by_regime.csv`
- `classification_by_regime.csv`
- `combined_signal_by_regime.csv`
- `ranking_by_regime.csv`
- `calibration_by_regime.csv`
- `run_config.json`
- `charts/`

## 8. Walk-Forward Regime-Aware Robustness

Purpose:

- Re-run the stack across multiple chronological folds to measure stability rather than single-window peak performance.

Default-style command:

```bash
python scripts/run_walk_forward_regime_robustness.py --tickers DGC ACB MWG HPG --train-start 2020-01-01 --first-eval-start 2023-01-01 --last-eval-end 2026-04-10 --eval-window-days 60 --step-size-days 30 --max-folds 4 --horizons 3d,5d,20d --algorithms cart,xgboost,lightgbm,sarimax,ets --output-dir artifacts/walk_forward_regime_robustness
```

Practical example matching the saved broader live run:

```bash
python scripts/run_walk_forward_regime_robustness.py --tickers DGC ACB MWG HPG --train-start 2020-01-01 --first-eval-start 2023-01-01 --last-eval-end 2026-04-10 --eval-window-days 60 --step-size-days 180 --max-folds 5 --algorithms cart,xgboost,lightgbm --output-dir artifacts/walk_forward_regime_robustness
```

Main outputs:

- `artifacts/walk_forward_regime_robustness/fold_001/` ... `fold_N/`
- `artifacts/walk_forward_regime_robustness/summary/fold_overview.csv`
- `artifacts/walk_forward_regime_robustness/summary/model_stability_summary.csv`
- `artifacts/walk_forward_regime_robustness/summary/horizon_stability_summary.csv`
- `artifacts/walk_forward_regime_robustness/summary/regime_stability_summary.csv`
- `artifacts/walk_forward_regime_robustness/summary/combined_method_stability_summary.csv`
- `artifacts/walk_forward_regime_robustness/summary/overall_robustness_report.csv`

## 9. Regime-Conditioned Meta-Selector

Purpose:

- Select candidate setups by regime using prior folds only.

Command:

```bash
python scripts/run_meta_selector.py --walk-forward-dir artifacts/walk_forward_regime_robustness --output-dir artifacts/meta_selector --selector-modes simple_regime_lookup,regime_weighted_rank,fallback_global --minimum-prior-folds-per-regime 2 --minimum-samples-per-regime 30 --primary-top-k 3
```

Main outputs:

- `artifacts/meta_selector/fold_001/` ... `fold_N/`
- `artifacts/meta_selector/summary/meta_selector_overview.csv`
- `artifacts/meta_selector/summary/selector_stability_summary.csv`
- `artifacts/meta_selector/summary/selector_regime_summary.csv`
- `artifacts/meta_selector/summary/selector_vs_baselines_summary.csv`
- `artifacts/meta_selector/summary/overall_meta_selector_report.csv`

## 10. Benchmark Audit and Context-Conditioned Meta-Selector

Purpose:

- Audit selector baselines and test richer context-conditioned selection modes.

Command:

```bash
python scripts/run_context_meta_selector.py --walk-forward-dir artifacts/walk_forward_regime_robustness --meta-selector-dir artifacts/meta_selector --audit-output-dir artifacts/meta_selector_audit --output-dir artifacts/context_meta_selector --selector-modes context_knn_selector,context_bin_lookup,context_meta_score
```

Main outputs:

- `artifacts/meta_selector_audit/benchmark_audit_report.csv`
- `artifacts/meta_selector_audit/baseline_definition_check.csv`
- `artifacts/meta_selector_audit/entity_comparison_trace.csv`
- `artifacts/context_meta_selector/fold_001/` ... `fold_N/`
- `artifacts/context_meta_selector/summary/context_selector_overview.csv`
- `artifacts/context_meta_selector/summary/context_selector_stability_summary.csv`
- `artifacts/context_meta_selector/summary/context_selector_vs_baselines_summary.csv`
- `artifacts/context_meta_selector/summary/context_selector_vs_regime_summary.csv`
- `artifacts/context_meta_selector/summary/context_feature_importance_summary.csv`
- `artifacts/context_meta_selector/summary/overall_context_selector_report.csv`

## Notes on Reproducibility

- The CLI defaults are deterministic where the underlying model family allows it.
- All recent research workflows enforce time ordering and save `run_config.json` files so split and cost assumptions can be audited later.
- If a workflow prints skipped algorithms, treat the saved ranking as conditional on the available environment, not as a universal ranking across all possible model families.
