# HackAIthon MVP Engine Spec

## Engine 1 Scope

Engine 1 is a static evidence, model-diagnostic metadata, and generated engine-catalog layer. It contains the Static Evidence Loader, concrete non-QML model diagnostic inventory, metadata-only adapter skeletons, generated baseline/support/stack engine specs, and a lightweight static-evidence runner.

It does not connect to providers, build a Data Gateway, train models, run inference, or rerun benchmarks.

QML is excluded from the HackAIthon MVP scope.

## Model Inventory Architecture

The inventory is built from archived local repository evidence. The primary source is `reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv`, which lists 75 non-QML model variants from the comprehensive VN30 model-universe benchmark. Additional regression and BiLSTM entries are included only because legacy reports, configs, or generated summaries reference them directly.

Allowed MVP families are:

- `baseline`
- `classification`
- `regression`
- `statistical`
- `ensemble_regime`
- `deep_learning`

Each concrete model has one adapter file named `<model_key>_diagnostic.py`. Each class uses the PascalCase model key plus `DiagnosticAdapter`, inherits `BaseDiagnosticAdapter`, and exposes metadata only.

Adapters are not runnable engines. A generated baseline engine instance combines adapter metadata with a target, horizon, feature set, policy, split policy, evidence mode, claim scope, and dependency metadata.

## Folder Structure

```text
src/hackaithon_mvp/model_diagnostics/
  base.py
  registry.py
  inventory.py
  baseline/
  classification/
  regression/
  statistical/
  ensemble_regime/
  deep_learning/
src/hackaithon_mvp/engine_runtime/
  engine_spec.py
  engine_id.py
  engine_result.py
  engine_registry.py
  engine_runner.py
  output_store.py
  dependency_policy.py
src/hackaithon_mvp/engine_catalog/
  baseline_catalog_generator.py
  support_catalog_generator.py
  stack_catalog_generator.py
  catalog_writer.py
  catalog_loader.py
```

## Adapter Contract

Adapters expose `model_key`, `display_name`, `model_family`, `supported_targets`, `supported_horizons`, `diagnostic_scope`, `is_exploratory`, `dependency_status`, `source_paths`, `summarize_family_constraints()`, and `to_metadata()`.

There is no model execution method on adapters. Runtime execution belongs to generated engine specs and the static MVP runner.

## Engine Runtime Contract

Generated engine specs use one of three engine types:

- `baseline`: concrete runnable diagnostic unit for one model/target/horizon/feature/policy combination.
- `support`: diagnostic unit that consumes dependency outputs and emits supporting evidence/risk labels.
- `stack`: governed combiner that consumes primitive or support outputs through a selection policy.

Engine catalogs are generated from adapter manifests and fixed MVP dimensions, not manually written per engine. Baseline engines can run independently when matching static evidence exists. Support and stack engines can run independently when dependency outputs are available; otherwise they skip safely and record missing dependency status.

The current run mode is `static_evidence_mvp`.

## Static Evidence Loader

`src/hackaithon_mvp/static_evidence_loader.py` loads local JSON sample evidence and validates that every record references a registered model key, matches the adapter family, and uses the adapter display name. Dependency-gated models are accepted only as metadata-only static demo records.

The engine runner synthesizes baseline diagnostic results only from matching local static evidence by `model_key`, target, and horizon.

## Catalog Artifacts

Full engine catalogs are generated artifacts and are not tracked in Git. The repository tracks generator code, catalog summaries, a generation manifest, and small sample catalogs. This keeps the HackAIthon MVP codebase lightweight while preserving reproducibility.

Tracked catalog artifacts live under `catalogs/hackaithon_mvp/`:

- `catalog_generation_manifest.json`
- `baseline_engine_catalog_summary.md`
- `support_engine_catalog_summary.md`
- `stack_engine_catalog_summary.md`
- `samples/*_sample.jsonl`

Catalog counts:

- Baseline engines: 32,850
- Support engines: 22,500
- Stack engines: 22,500

Regenerate full local JSONL catalogs with `python -m src.hackaithon_mvp.engine_catalog.catalog_writer`. Generated full JSONL catalogs are ignored by Git. The catalogs exclude QML and quantum scope, Data Gateway behavior, live data access, provider calls, training, inference, benchmark reruns, and public recommendation language.
