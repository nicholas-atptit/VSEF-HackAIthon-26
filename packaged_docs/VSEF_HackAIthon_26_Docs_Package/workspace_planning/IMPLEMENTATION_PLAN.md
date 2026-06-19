# HackAIthon MVP Implementation Plan

## Current Slice

Engine 1 includes the Static Evidence Loader plus concrete non-QML Model Inventory and Adapter Skeletons. This slice creates the metadata foundation needed by later forecast diagnostics without executing any model.

QML is excluded from the HackAIthon MVP scope.

## In Scope

- Static sample evidence JSON.
- Metadata-only BaseDiagnosticAdapter contract.
- Concrete adapter files grouped by allowed model family.
- Registry helpers for lookup, family filtering, exploratory filtering, and dependency-gated filtering.
- Inventory documentation generated from legacy evidence paths.
- Tests for registry integrity, adapter naming, static evidence validation, and forbidden MVP scope leaks.

## Out of Scope

- Data Gateway.
- Live data fetches.
- Provider API calls.
- Model training.
- Model inference.
- Benchmark reruns.
- Public demo output beyond static metadata evidence.

## Next Implementation Steps

1. Build a Forecast Diagnostic Engine that consumes the non-QML registry and static evidence records.
2. Add reviewer-facing summary schemas that reference registry metadata without executing model code.
3. Add API or dashboard contracts only after the diagnostic schema is stable.
4. Keep source evidence and claim boundaries explicit in every reviewer-facing output.
