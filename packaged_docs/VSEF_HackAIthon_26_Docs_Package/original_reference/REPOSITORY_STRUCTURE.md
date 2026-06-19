# Repository Structure

VSEF separates reusable research code, one-off research runners, validation, documentation, and preserved evidence.

## Research Flow

```text
Local historical/cache data
-> data loaders / provider contracts
-> point-in-time feature builders
-> target builders
-> split policy
-> model/evaluation layer
-> validation-only selector
-> forecast panel generator
-> reports / generated evidence
-> claim boundary
```

## Reusable Code

| Path | Responsibility |
|---|---|
| `src/data/` | Provider contracts, adapters, local loaders, and data validation |
| `src/features/` | Point-in-time-safe feature builders |
| `src/evaluation/` | Direction, return/price, interval, ranking metrics, and baselines |
| `src/forecasting/` | Offline forecast panels, validation-only selectors, and engine implementation |
| `src/governance/` | Split, claim-boundary, and artifact policies |
| `src/utils/` | Paths, timestamps, serialization, logging, and manifests |

Existing `src/ml/`, `src/forecast/`, `src/engine/`, and diagnostic-chain packages remain supported. Their paths are retained because tests, scripts, and evidence depend on them.

## Runners, Tests, and Configuration

- `scripts/research/`: research, audit, and benchmark orchestration.
- `scripts/research/run_vn_forecast_engine_v1.py`: offline latest-cache, historical-as-of, evaluation-only, and full forecast-engine runner.
- `scripts/check_*.py`: repository, runtime, and provider-policy validation.
- `tests/`: unit, integration, contract, and governance tests.
- `configs/`: active research and validation configuration.
- `config/`: retained runtime configuration where existing imports depend on it.

Heavy Model Universe runners remain one-off orchestrators. Reusable logic belongs under `src/`.
QML is excluded from the HackAIthon MVP scope.

## Evidence and Artifacts

- `reports/_index/ACTIVE_EVIDENCE_INDEX.md`: active evidence navigation.
- `reports/results/`, `reports/claims/`, `reports/protocols/`: result and governance evidence.
- `reports/generated/`: preserved generated diagnostic evidence.
- `reports/generated/vn_forecast_engine_v1/`: forecast panels, audits, evaluations, model registry, and decision JSON.
- `reports/generated/vn30_model_universe_direction_price/`: Model Universe direction and return/price evidence.
- `reports/paper/`: paper-source materials where present.
- `data/`, `outputs/`, `archive/`: protected local data and evidence roots.

See `docs/governance/DATA_AND_ARTIFACT_POLICY.md` before moving or deleting any artifact.

The requested `reports/project_review/`, `reports/generated/vn30_index_group_range_forecast/`, and dedicated V7 result-summary paths are not present on this branch. Do not cite them as available evidence or invent their results.
