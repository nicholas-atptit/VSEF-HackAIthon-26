# ML Implementation Guide
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Usage guide |
| Created / authored | Wednesday, 2026-04-15 11:19:48 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-04-28 22:51:14 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `ef20ce73b466d75a61ca4768d4f4129405df7fb0` |
| Timestamp source | Git history |
| Status | Active |

This guide explains how the current ML system is wired internally.

It is intended for developers and reviewers who need to understand:

- how data moves through the repository
- where targets and labels are created
- how horizons are handled
- how training and inference reuse the same trainer path
- how later evaluation layers build on saved artifacts without redesigning the core stack

## 1. High-Level Architecture

The current stack is layered rather than monolithic.

```text
vnstock OHLCV / benchmark data
    -> schema normalization
    -> feature engineering
    -> target generation in trainer
    -> model training / manifest writing
    -> per-horizon inference
    -> regression + classification evaluation
    -> combined-signal analysis
    -> regime-aware slicing
    -> walk-forward robustness summaries
    -> selector experiments
```

Core implementation modules:

- `src/data/adapters/vnstock_adapter.py`
- `src/ml/feature_engineering.py`
- `src/ml/trainer.py`
- `src/ml/backtest/real_data.py`
- `src/ml/backtest/model_comparison.py`
- `src/ml/backtest/forward_return.py`
- `src/ml/backtest/dual_task.py`
- `src/ml/backtest/combined_signal.py`
- `src/ml/backtest/regime_aware_analysis.py`
- `src/ml/backtest/walk_forward_regime_robustness.py`
- `src/ml/backtest/meta_selector.py`
- `src/ml/backtest/context_meta_selector.py`

## 2. Data Flow

### 2.1 Market data

`VnstockAdapter` is the main acquisition wrapper.

Responsibilities:

- fetch ticker OHLCV from `vnstock`
- normalize to `date,ticker,open,high,low,close,volume`
- clamp data to the requested date range
- sort ascending by date
- remove duplicate dates
- coerce numeric columns
- retry transient failures

Benchmark and regime workflows reuse the same adapter for `VNINDEX` where possible and fall back to a market-proxy file path when configured.

### 2.2 Context data

`src/ml/trainer.py` loads optional context sources through:

- `load_market_proxy()`
- `load_sector_proxies()`
- `load_ticker_sectors()`
- `load_sentiment()`

The trainer merges context into the OHLCV frame before feature engineering. Forward fill is allowed; backward fill is deliberately avoided in the main merge path to prevent future leakage.

## 3. Feature Engineering

`FeatureEngineer` in `src/ml/feature_engineering.py` is the shared transformation layer for training and inference.

Key implementation details:

- input rows are sorted by `date`
- `close_raw` is preserved before downstream transformations
- external context is merged before feature generation
- all rolling indicators use only historical rows
- `drop_na=True` is used for training-ready feature frames so warmup rows are removed explicitly

Main feature groups currently present:

- close-to-close returns and lagged returns
- open-to-close and overnight returns
- rolling close means and rolling close standard deviations
- rolling volatility features
- high-low range, true range, ATR-style features
- rolling volume averages, ratios, and shocks
- RSI and MACD features
- Bollinger-style features
- delta features across numeric columns
- optional market, sector, sentiment, risk, and regime columns

The richer daily forecasting features recently added live inside this shared feature layer, so the same columns are available to fixed-window backtests, forward-return workflows, dual-task workflows, and selector analyses.

## 4. Target and Label Generation

Target creation is centralized in `DualModelTrainer._add_targets(...)` inside `src/ml/trainer.py`.

That function augments the prepared feature frame with per-horizon targets and metadata.

### 4.1 Horizon handling

The trainer resolves named horizons to trading-day counts through a horizon-day map.

The currently active research horizons are:

- `3d -> 3`
- `5d -> 5`
- `20d -> 20`

The code keeps horizon names explicit in manifests and artifact paths, which makes later evaluation layers simpler and less error-prone.

### 4.2 Regression targets

Forward-return regression targets are created as:

- `target_return_3d = close.shift(-3) / close - 1`
- `target_return_5d = close.shift(-5) / close - 1`
- `target_return_20d = close.shift(-20) / close - 1`

The trainer also stores:

- `target_date_{horizon}`
- `target_direction_{horizon}`

This is important because later evaluation windows are enforced on realized `target_date`, not only on the anchor row.

### 4.3 Classification targets

Profit/loss labels are cost-aware and are also created in `DualModelTrainer._add_targets(...)`.

Implementation logic:

- entry date: next tradable session, `date.shift(-1)`
- entry price: next tradable open, `open.shift(-1)`
- exit date: realized target date, `date.shift(-horizon_days)`
- exit price: target-date close, `close.shift(-horizon_days)`

Net trade return is computed with:

- `transaction_fee_bps`
- `slippage_bps`
- costs applied on entry and exit

The helper used is `DualModelTrainer.calculate_net_trade_return_series(...)`.

Profit labels are then defined as:

- `target_profit_label_{horizon} = 1 if target_net_return_{horizon} > 0 else 0`

This makes the classification branch explicitly about tradability after costs rather than raw return sign.

## 5. Training Path

`DualModelTrainer` is the main training and inference facade.

Important internal structures:

- `PreparedTickerData`
- `SplitDefinition`
- model manifests written through `src/ml/artifacts.py`

### 5.1 Prepared data

`prepare_ticker_data(...)` does the following:

- normalize OHLCV
- restrict to the requested data window plus warmup buffer
- add context features
- run `FeatureEngineer.transform(...)`
- optionally add risk and regime features
- record data coverage and warmup loss statistics

### 5.2 Explicit split training

The recent research workflows use `train_explicit_split(...)` rather than inventing disconnected training logic.

That method enforces:

- explicit `train_start`
- explicit `train_end`
- explicit horizon name and horizon day count
- manifest-driven artifact writing

The backtest layers reuse this trainer call rather than bypassing the model registry.

### 5.3 Algorithm families

The trainer supports both tabular and sequence paths.

Tabular:

- `cart`
- `xgboost`
- `lightgbm`
- optional statistical families where supported

Sequence-aware:

- `lstm`
- `bilstm`

The same trainer handles both, but sequence algorithms go through `src/ml/sequence_dataset.py` while tabular algorithms stay in flat feature space.

### 5.4 Manifests and artifacts

Per-model manifests record:

- algorithm
- feature columns
- target type
- horizon days
- split metadata
- artifact locations
- advanced risk configuration if used

This matters because later inference and evaluation layers reload models by manifest instead of reconstructing training assumptions manually.

## 6. Inference Path

Inference also goes through `DualModelTrainer.predict(...)`.

The backtest runners rebuild feature history up to the current anchor date, then request predictions for:

- a specific ticker
- a specific horizon
- a specific algorithm

The trainer returns:

- `predicted_return`
- `predicted_direction`
- `predicted_profit_label` when the profit classifier is available
- `predicted_profit_probability` when probability output is available

This keeps the downstream workflows decoupled from model-family-specific APIs.

## 7. Evaluation Layers

The modern evaluation stack is layered deliberately.

### 7.1 `real_data.py`

Purpose:

- fixed-window close-level backtest
- compare against naive previous-close baseline

### 7.2 `model_comparison.py`

Purpose:

- compare model families on the same fixed-window backtest

### 7.3 `forward_return.py`

Purpose:

- evaluate forward-return regression across `3d`, `5d`, and `20d`
- write per-horizon metrics, rankings, and model comparison artifacts

Important design choice:

- evaluation window is enforced on realized `target_date`
- `prediction_date` is `target_date minus horizon trading days`
- rankings in this layer compare forecast error and sign accuracy on the same forward-return task only
- they do not measure portfolio PnL quality or uncertainty calibration quality

### 7.4 `strategy_backtest.py`

Purpose:

- transform saved forward-return outputs into analysis-only threshold strategies

Execution assumptions are explicit in `run_config.json`:

- signal time: `prediction_date close`
- entry: next trading session open
- exit: `target_date close`
- non-overlapping positions by default
- transaction costs and slippage applied on both entry and exit

### 7.5 `dual_task.py`

Purpose:

- evaluate regression and cost-aware classification together
- write branch-specific and joined artifacts

The joined output in `artifacts/dual_task/summary/joined_regression_classification_evaluation.csv` is the key handoff to the combined-signal layer.

### 7.6 `combined_signal.py`

Purpose:

- build analysis-only signal quality views from:
  - `predicted_return`
  - `predicted_profit_probability`

Implemented combination styles include:

- weighted linear score
- gated threshold logic
- rank-based combination

It produces:

- combined signal tables
- bucket summaries
- top-k ranking summaries
- calibration summaries

### 7.7 `regime_aware_analysis.py`

Purpose:

- attach `bull`, `bear`, or `sideway` to saved outputs
- compare regression, classification, and combined-signal behavior by regime

Safe alignment detail:

- regimes are assigned using data available up to `prediction_date`
- benchmark merges are backward-looking, not future-looking

### 7.8 `walk_forward_regime_robustness.py`

Purpose:

- rerun the stack across repeated chronological folds
- summarize cross-fold stability

It reuses the existing runners rather than reimplementing the forecasting logic.

### 7.9 `meta_selector.py`

Purpose:

- choose candidate setups by regime using prior folds only

Current candidate tuple:

- `model_name`
- `horizon`
- `ranking_method`
- thresholds when the combined method is gated

The selector does not yet switch regression and classification models independently as separate components.

### 7.10 `context_meta_selector.py`

Purpose:

- audit selector baselines
- test context-conditioned selectors that use richer continuous market and prediction-state features

## 8. Trust Boundaries

The canonical research path is:

- `src.ml.trainer.DualModelTrainer`
- manifest-driven inference via `src.ml.inference.engine.InferenceEngine`
- fixed-window benchmark layers under `src.ml.backtest`

Interpretation boundaries:

- `heuristic_scenario_risk` is a residual-based scenario layer around the point forecast
- scenario `VaR` and `CVaR` values are simulated tail summaries, not calibrated forecast confidence and not guaranteed loss bounds
- validation metrics, held-out test metrics, and backtest metrics are intentionally stored with explicit split semantics and should not be compared as if they came from the same evaluation regime
- model-comparison artifacts rank comparable shared prediction tasks only; they do not provide a single unified truth ranking across prediction quality, portfolio performance, and uncertainty quality

## 9. Artifact Schema Versioning

Modern ML manifests now carry:

- `manifest_schema_version`
- `compatibility_version`
- `artifact_created_by`

Loader policy:

- current manifests use the latest schema version
- recently older manifests are normalized on load with backward-compatible defaults for risk semantics and evaluation metadata
- deprecated compatibility surfaces such as `risk_assessment` remain additive aliases, not canonical output names

## 10. Recommended Validation Path

Before demo or research use, run:

```bash
python scripts/verify_ml_baseline.py --skip-inference
```

Use `--full-suite` only when the local environment can run the full `tests/ml/` tree cleanly. The focused gate is the intended reliability subset for the canonical modern path.

It still builds on saved walk-forward and meta-selector artifacts instead of introducing a separate framework.

## 8. No-Leakage and Time-Series Safety

The repository now has several layers of time-safety controls.

### 8.1 Feature safety

- rolling features only use historical values
- context merges use forward fill, not backward fill, in the main training path
- feature generation happens before future targets are attached

### 8.2 Split safety

- fixed-window workflows use explicit train and eval boundaries
- forward-return and dual-task workflows evaluate on realized `target_date`
- walk-forward folds are strictly chronological

### 8.3 Label safety

- forward returns use `shift(-horizon)` only for target construction
- profit labels use next tradable open and target-date close
- no future rows are used in current-row features

### 8.4 Regime safety

- regimes are based on benchmark history available at or before `prediction_date`
- no future benchmark data is used to classify the current row

### 8.5 Selector safety

- regime-conditioned and context-conditioned selectors use prior folds only
- later fold results never influence earlier selections
- fold `001` is treated as insufficient history rather than silently borrowing future information

## 9. Recommended Mental Model

The cleanest way to think about the current architecture is:

1. `vnstock_adapter.py` fetches and standardizes market data.
2. `feature_engineering.py` builds reusable daily features.
3. `trainer.py` creates horizon-aware targets and fits manifests.
4. `forward_return.py` and `dual_task.py` generate the primary evaluation artifacts.
5. `combined_signal.py` merges the two forecast branches.
6. `regime_aware_analysis.py` explains conditional behavior by market state.
7. `walk_forward_regime_robustness.py` checks whether those findings repeat.
8. `meta_selector.py` and `context_meta_selector.py` test adaptive selection ideas on top of those saved results.

That layered design is the main implementation strength of the repo today: new evaluation ideas were added by extending artifact-driven workflows instead of replacing the core trainer or inventing parallel systems.
