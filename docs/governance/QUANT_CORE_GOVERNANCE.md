# Quant Core Governance
## Document Metadata

| Field | Value |
| --- | --- |
| Document type | Governance note |
| Created / authored | Tuesday, 2026-04-28 22:34:05 ICT (UTC+07:00) |
| Last updated | Tuesday, 2026-05-05 00:00:00 ICT (UTC+07:00) |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Branch | `vsef-doc-datetime-metadata-standardization` |
| Commit | `5ceed8162b4658cd1ee3402fb147aa5246c1f540` |
| Timestamp source | Local deterministic decision-chain documentation refactor |
| Status | Active |

## Purpose

This document governs the active deterministic decision-diagnostic chain. Quant
Core turns forecast, regime, risk, and policy-evaluation diagnostics into
analysis-ready artifacts with:

- explicit model roles
- explicit run modes
- reproducible manifests
- analysis-ready outputs
- clean separation between full-zoo execution and narrower research or decision
  subsets

Quant Core is not a recommendation layer. Its outputs are forecast diagnostics,
consensus diagnostics, health diagnostics, packet diagnostics, and conservative
candidate diagnostics for downstream diagnostic layers.

The implementation keeps the full current quant-core forecast zoo available in
`full_forecast` mode. It does not remove any currently supported forecast model
family from the walk-forward quant-core lane.

## Implemented Diagnostic Chain

The current implemented diagnostic chain is:

`Quant Core -> Scenario Evaluation -> Risk Governance -> Decision Lane v2 -> Portfolio Allocator v1 -> Phase 3 Router v1`

Each layer remains diagnostic-only:

- Scenario Evaluation Engine v1 emits scenario diagnostics.
- Risk Governance Layer v1 emits risk diagnostics and candidate risk actions.
- Decision Lane v2 emits enriched diagnostic candidates.
- Portfolio Allocator v1 emits `allocation_candidate` or `no_allocation`.
- Phase 3 Router v1 emits `route_allocation_candidate`, `hold`, `reject`, or
  `no_candidate`.

No layer emits BUY or SELL recommendations, live execution instructions,
production trading authority, or learned meta-model authority.

## Governance Rules

1. Full model-zoo presence remains intact for the current quant-core forecast
   registry.
2. Diagnostic-chain participation is role-aware rather than implied by ad hoc
   model lists.
3. Run-mode behavior is explicit and recorded in the manifest.
4. Research narrowing does not delete weaker models; it demotes them to
   `comparator`, `baseline_only`, or `shadow_only`.
5. Unsupported environment dependencies are surfaced explicitly in
   `skipped_models` and `model_execution_log`.
6. Risk and regime fallbacks are explicit in outputs:
   `var_cvar_drawdown_fallback` and
   `markov_switching_threshold_fallback`.

## Current Model Roles

| model_name | family | role | status | full_forecast | research_core | decision_core | notes |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| `lightgbm` | boosting | `primary_research` | active | 1 | 1 | 1 | Current primary research model in the narrow edge lane. |
| `xgboost` | boosting | `primary_research` | active | 1 | 1 | 1 | Current primary research model in the narrow edge lane. |
| `random_forest` | tree | `primary_research` | active | 1 | 1 | 1 | Tree-based primary research model retained in the diagnostic decision subset. |
| `ets` | statistical | `comparator` | active | 1 | 1 | 0 | Statistical comparator retained for research-lane benchmarking. |
| `sarimax` | statistical | `comparator` | active | 1 | 1 | 0 | Time-series comparator retained for research-lane benchmarking. |
| `naive` | baseline | `baseline_only` | baseline | 1 | 0 | 0 | Baseline checkpoint for full-zoo and baseline-only runs. |
| `moving_average` | baseline | `baseline_only` | baseline | 1 | 0 | 0 | Baseline checkpoint for full-zoo and baseline-only runs. |
| `linear` | linear | `shadow_only` | shadow | 1 | 0 | 0 | Preserved in the full zoo for continuity but not in the active research core. |
| `ridge` | linear | `shadow_only` | shadow | 1 | 0 | 0 | Preserved in the full zoo for continuity but not in the active research core. |
| `lasso` | linear | `shadow_only` | shadow | 1 | 0 | 0 | Preserved in the full zoo for continuity but not in the active research core. |

## Run Modes

| run_mode | semantic intent | included roles |
| --- | --- | --- |
| `full_forecast` | Run the full supported quant-core forecast zoo and collect full analysis outputs. | `primary_research`, `comparator`, `baseline_only`, `shadow_only` |
| `research_core` | Focus the run on the current research lane. | `primary_research`, `comparator` |
| `decision_core` | Restrict execution to the current diagnostic decision subset. | `primary_research` models flagged for diagnostic decision-chain use |
| `baseline_only` | Run checkpoint baselines only. | `baseline_only` |

## Presets

The top-level runner currently supports:

- `smoke`
- `medium`
- `full_forecast_daily`

Presets control ticker groups, horizons, target sets, and walk-forward window
configuration. Run mode remains a separate explicit control.

## Runner

Primary entry point:

`python scripts/run_quant_core.py`

Examples:

- `python scripts/run_quant_core.py --preset smoke --run-mode research_core`
- `python scripts/run_quant_core.py --preset full_forecast_daily --run-mode full_forecast`
- `python scripts/run_quant_core.py --tickers ACB BID CTG MBB --horizons 5 10 --target-types forward_return direction_binary --run-mode decision_core`
- `python scripts/run_quant_core.py --preset medium --run-mode baseline_only --no-ensemble`

Smoke-run validation for `research_core`, `baseline_only`, and `decision_core`
is documented in `docs/audits/VSEF_QUANT_CORE_SMOKE_AUDIT.md`.

## Reused Components

- `WalkForwardEvaluator` for leakage-safe forecast execution
- `ForecastModel` contract and current forecast implementations
- `GARCHRiskModel` contract, with explicit historical fallback when `arch` is not
  available
- `MarkovSwitchingRegimeModel` contract, with explicit threshold fallback when
  `statsmodels` is not available
- `execute_policy_configuration` and `CostAwareBacktester`
- existing manifest, summary, and target-spec infrastructure

## Added Components

- `src/core/model_governance.py`
- governed `src/forecast/registry.py`
- `src/evaluation/quant_core.py`
- `scripts/run_quant_core.py`
- `src/evaluation/consensus.py`
- `src/reporting/analysis_packets.py`
- `src/reporting/model_health.py`
- `src/reporting/quant_core.py`
- `src/scenario`
- `src/risk_governance`
- `src/reporting/decision_lane.py`
- `src/portfolio_allocator`
- `src/phase3_router`

## Out Of Scope

The active deterministic chain still keeps these out of scope:

- new forecast model families
- learned meta-model decision logic unless explicitly implemented in a future
  governed layer
- deep sequence-model rollout into the current walk-forward quant-core lane
- claims of broad robust edge
- BUY or SELL recommendation authority
- live execution or production trading readiness
