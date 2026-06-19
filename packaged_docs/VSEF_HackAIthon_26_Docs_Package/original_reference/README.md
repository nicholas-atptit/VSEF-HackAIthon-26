# VSEF HackAIthon 2026 MVP Workspace

**Research-only** | **Offline historical/local-data-first** | **Diagnostic framework** | **No trading authority**

This repository is the dedicated HackAIthon 2026 MVP workspace for VSEF. It is derived from the VSEF research framework and is being adapted into a conservative banking research and risk-review demo context.

Vietcombank is used only as the product-facing banking evaluation context for the HackAIthon use case. This does not imply Vietcombank sponsorship, deployment, approval, endorsement, or partnership. Viettel Global remains separate as research attribution for the underlying research work only.

## Current MVP Slice

Current MVP slice: Static Evidence Loader + concrete non-QML model diagnostic inventory. The repository now separates model families and concrete non-QML model types into small adapter files under `src/hackaithon_mvp/model_diagnostics/`. These adapters are metadata-only and do not train, infer, or produce trading recommendations. QML is excluded from the HackAIthon MVP scope.

## Claim Boundary

VSEF remains research-only and diagnostic-only. The HackAIthon MVP does not provide broker execution, live execution, production readiness, profitability guarantees, autonomous decisions, or investment advice.

Default operation is offline historical/local-data-first unless explicitly revised under a written protocol.

## Engine 1 Components

- `src/hackaithon_mvp/static_evidence_loader.py`: validates static local sample evidence.
- `src/hackaithon_mvp/model_diagnostics/`: metadata-only adapter registry and concrete non-QML adapter files.
- `examples/hackaithon_mvp/sample_evidence.json`: static demo records for the MVP workflow.
- `docs/hackaithon_mvp/MODEL_INVENTORY_FROM_LEGACY.md`: source-backed non-QML model inventory.
- `docs/hackaithon_mvp/MVP_ENGINE_SPEC.md`: Engine 1 architecture and constraints.
- `docs/hackaithon_mvp/IMPLEMENTATION_PLAN.md`: first-slice implementation plan and next steps.

## Safe Validation

```powershell
python -m pytest tests/hackaithon_mvp -q
python scripts/check_repo_hygiene.py
python scripts/check_runtime_preflight.py
```

These checks are intended to be local and light. They do not fetch live data, call provider APIs, train models, or rerun benchmarks.

## Evidence References

- `reports/generated/vn30_model_universe_benchmark/model_universe_registry.csv`
- `reports/generated/vn30_model_universe_benchmark/audit_result.md`
- `reports/generated/vn30_model_universe_benchmark/model_universe_claim_boundary.md`
- `reports/results/VN30_FULL_MODEL_TUNING_V3_RESULT_SUMMARY.md`
- `reports/results/VN30_MODEL_UNIVERSE_V1_V6_CLOSEOUT_REPORT.md`
- `reports/results/VN30_MODEL_UNIVERSE_V6_PRICE_RETURN_ABSOLUTE_CONFIRMATION_RESULT_SUMMARY.md`

## Development Rules

- Work in this HackAIthon repository, not the original VSEF research repository.
- Do not fetch live data or call provider APIs without a written protocol.
- Do not run heavy benchmarks during MVP cleanup or static evidence work.
- Do not convert diagnostics into investment instructions.
- Keep Vietcombank and Viettel Global stakeholder roles separate.
- Preserve active evidence and claim-boundary files.
