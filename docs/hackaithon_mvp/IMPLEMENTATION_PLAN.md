# HackAIthon MVP Implementation Plan

## Current Slice

Engine 1 includes the Static Evidence Loader, concrete non-QML Model Inventory, Adapter Skeletons, generated engine catalogs, and a lightweight static-evidence runner. This slice creates the metadata and runtime foundation needed by later forecast diagnostics without training or running model inference.

QML is excluded from the HackAIthon MVP scope.

## In Scope

- Static sample evidence JSON.
- Metadata-only BaseDiagnosticAdapter contract.
- Concrete adapter files grouped by allowed model family.
- Generated baseline engine specs from adapter metadata, targets, horizons, feature sets, and policies.
- Generated support and stack engine specs for future DAG execution.
- Static MVP runner for one engine spec.
- JSON output store for small run manifests and result JSONL.
- Registry helpers for lookup, family filtering, exploratory filtering, and dependency-gated filtering.
- Inventory documentation generated from legacy evidence paths.
- Tests for registry integrity, adapter naming, static evidence validation, generated catalogs, engine IDs, runner behavior, output store writes, and forbidden MVP scope leaks.

## Out of Scope

- Data Gateway.
- Live data fetches.
- Provider API calls.
- Model training.
- Model inference.
- Benchmark reruns.
- Data-driven DAG execution.
- Public demo output beyond static evidence diagnostics.

## Next Implementation Steps

1. Add a DAG runner that executes generated baseline, support, and stack graphs while preserving dependency lineage.
2. Integrate the engine runtime with the Forecast Diagnostic Engine.
3. Add reviewer-facing summary schemas that reference registry and engine metadata without invoking training or provider access.
4. Add API or dashboard contracts only after the diagnostic schema is stable.
5. Keep source evidence and claim boundaries explicit in every reviewer-facing output.
