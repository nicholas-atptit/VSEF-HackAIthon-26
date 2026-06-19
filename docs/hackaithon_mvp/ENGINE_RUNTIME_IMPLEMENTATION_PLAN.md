# Engine Runtime Implementation Plan

## Why Adapters Are Not Enough

The current model adapters are metadata contracts for concrete model types. They identify model keys such as `logistic_l2`, `random_forest`, `ridge_regression`, `arima_direction`, and `bilstm`, but they do not define a target, horizon, feature set, calibration policy, split policy, evidence mode, dependency lineage, or runnable result contract.

The MVP therefore needs generated engine specs. An engine spec turns a metadata adapter into a concrete diagnostic unit that can be run independently in static evidence mode.

## Runtime Concepts

- Model adapter: metadata for one concrete in-scope model type. It has no training, inference, provider, or execution method.
- Baseline engine instance: a runnable diagnostic unit built from `model_key`, target, horizon, feature set, threshold or calibration policy, split policy, and evidence mode.
- Support engine: a diagnostic unit that consumes other engine outputs and emits supporting risk/evidence signals such as model disagreement, baseline edge, class balance risk, liquidity risk, regime instability, drift risk, evidence strength, and scope mismatch.
- Stack engine: a governed combiner that consumes primitive and support outputs using validation-top-k vote, weighted vote, family-diverse vote, risk-adjusted vote, scenario-weighted vote, baseline-gated stack, or confidence-weighted stack policies.
- DAG runner: the later runner that will execute engine graphs while preserving dependency lineage, skip reasons, and claim-boundary governance.

## Generated Catalogs

Baseline engines are generated from discovered in-scope adapters by crossing:

- `model_key`
- target
- horizon
- feature set
- policy

This produces many more runnable units than the 83 metadata adapters because each adapter can validly appear across multiple targets, horizons, feature scopes, and static policies. The generator reports the actual count instead of forcing a predetermined number.

Support and stack engines are also generated from manifests. Support engines cross support type, universe, target, horizon, feature scope, and model family. Stack engines cross stack type, target, horizon, feature set, selection policy, and dependency policy. This allows thousands of support/stack specs without hand-written files.

Full engine catalogs are generated artifacts and are not tracked in Git. The repository tracks generator code, catalog summaries, a generation manifest, and small sample catalogs. This keeps the HackAIthon MVP codebase lightweight while preserving reproducibility.

Catalog counts:

- Baseline engines: 32,850
- Support engines: 22,500
- Stack engines: 22,500

Full local JSONL catalogs can be regenerated with `python -m src.hackaithon_mvp.engine_catalog.catalog_writer`.

## Independent Execution

Every baseline engine can run independently in `static_evidence_mvp` mode. If matching local static evidence is available by `model_key`, target, and horizon, it returns a completed diagnostic result. If evidence is missing, it returns `skipped_missing_evidence`.

Every support or stack engine can run independently if its dependency outputs are supplied. If dependency outputs are absent, it returns `skipped_missing_dependency`. Dependency lineage is recorded through the spec `dependencies` field and the result `dependencies_used` field.

The current runner performs no model training, no model inference, no provider access, no live data fetch, and no benchmark rerun.

## Scope Boundaries

QML and quantum engine specs remain excluded. The validators reject excluded terms in engine IDs and metadata. No QML adapters, QML engines, QML stack nodes, or QML sample evidence are created.

A Data Gateway is out of scope for this slice. Future offline local-data execution can attach behind a governed engine interface, but this implementation only uses local static/sample evidence.

Diagnostic outputs remain research-only and do not produce trading, profitability, recommendation, allocation, live deployment, or production-readiness claims.
