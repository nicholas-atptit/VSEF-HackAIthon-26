# HackAIthon MVP Engine Spec

## Engine 1 Scope

Engine 1 is a static evidence and model-diagnostic metadata layer. It contains the Static Evidence Loader plus concrete non-QML model diagnostic inventory and adapter skeletons. It does not connect to providers, build a Data Gateway, train models, run inference, or rerun benchmarks.

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
```

## Adapter Contract

Adapters expose `model_key`, `display_name`, `model_family`, `supported_targets`, `supported_horizons`, `diagnostic_scope`, `is_exploratory`, `dependency_status`, `source_paths`, `summarize_family_constraints()`, and `to_metadata()`.

There is no model execution method in this MVP layer. A future implementation can attach actual model execution behind a separate governed interface while keeping this metadata registry stable.

## Static Evidence Loader

`src/hackaithon_mvp/static_evidence_loader.py` loads local JSON sample evidence and validates that every record references a registered model key, matches the adapter family, and uses the adapter display name. Dependency-gated models are accepted only as metadata-only static demo records.
