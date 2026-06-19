# VSEF v1 Project Tracker

## Document Metadata

| Field | Value |
| --- | --- |
| Document name | VSEF v1 Project Tracker |
| Phase | 0 |
| Status | Frozen for v1 |
| Last updated date | 2026-05-09 |
| Timezone | Asia/Ho_Chi_Minh / ICT (UTC+07:00) |
| Owner | Project team / maintainer |
| Document type | Governance tracker |

## Purpose

This tracker records Phase 0 governance tasks and prevents uncontrolled VSEF v1
scope expansion. Phase 0 is documentation-only. It does not add models, strategy
engines, portfolio allocation logic, agents, APIs, dashboards, data providers,
training pipelines, evaluation runtime behavior, database tables, or LLM
decision-making layers.

## Phase 0 Task Table

| Task ID | Task name | Status | Priority | Owner | Expected deliverable | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.1 | Freeze VSEF v1 architecture | Done | Critical | Project team / maintainer | Architecture freeze document | `docs/architecture/VSEF_v1_ARCHITECTURE.md` | Freezes layers, inclusions, exclusions, and decision-lane meaning. |
| 0.2 | Freeze supported models | Done | Critical | Project team / maintainer | Model registry | `docs/governance/MODEL_REGISTRY.md` | Freezes SARIMAX, ETS, XGBoost, LightGBM, LSTM, BiLSTM, and Stacking as the only supported v1 models. |
| 0.3 | Freeze data policy | Done | Critical | Project team / maintainer | Data provider and schema policy | `docs/governance/DATA_POLICY.md` | Freezes `vnstock_data`, daily OHLCV, schema, validation, and non-v1 data exclusions. |
| 0.4 | Freeze evaluation policy | Done | Critical | Project team / maintainer | Evaluation protocol | `docs/governance/EVALUATION_PROTOCOL.md` | Freezes time-series-safe evaluation and artifact evidence rules. |
| 0.5 | Create project tracker | Done | High | Project team / maintainer | Governance tracker | `docs/governance/PROJECT_TRACKER.md` | Tracks Phase 0 tasks and routes future ideas to backlog. |

## Status Legend

| Status | Definition |
| --- | --- |
| Not started | Work has not begun. |
| In progress | Work has begun but acceptance criteria or evidence are incomplete. |
| Done | Required deliverable exists, acceptance criteria are clear, and reviewable evidence path is present. Release sign-off requires the evidence to be committed. |
| Blocked | Work cannot proceed until a dependency, decision, or missing input is resolved. |
| Deferred | Work is intentionally moved out of current scope. |
| Out of scope | Work is explicitly outside frozen VSEF v1 and is not approved for Phase 0 or v1 implementation. |

## Priority Legend

| Priority | Definition |
| --- | --- |
| Critical | Required to freeze VSEF v1 scope or prevent material governance risk. |
| High | Important for reviewability, traceability, or implementation discipline. |
| Medium | Useful but not required for immediate Phase 0 acceptance. |
| Low | Nice-to-have documentation or cleanup. |

## Backlog: Deferred to v1.5

| Backlog item | Status | Priority | Owner | Evidence / future deliverable | Notes |
| --- | --- | --- | --- | --- | --- |
| Portfolio Allocator v1 implementation | Deferred | High | Project team / maintainer | Future allocator governance and implementation evidence | v1.5 or next implementation phase, not Phase 0. |
| Meta-model routing | Deferred | Medium | Project team / maintainer | Future model-routing proposal and validation evidence | Future phase only; not part of frozen VSEF v1. |
| Provider expansion beyond `vnstock_data` daily OHLCV | Deferred | Medium | Project team / maintainer | Future data-provider policy update | Must include schema, provenance, validation, and leakage controls. |
| Additional model families beyond the frozen registry | Deferred | Medium | Project team / maintainer | Future model registry change request | Must not enter v1 without governance approval. |

## Backlog: Deferred to v2

| Backlog item | Status | Priority | Owner | Evidence / future deliverable | Notes |
| --- | --- | --- | --- | --- | --- |
| Autonomous LLM decision agents | Deferred | High | Project team / maintainer | Future authority-boundary and safety review | v2 / out of v1; LLMs are not v1 forecasting models or decision makers. |
| Multi-asset institutional portfolio optimization | Deferred | Medium | Project team / maintainer | Future portfolio research design | Not part of VSEF v1 governance. |
| Real-time intraday trading architecture | Deferred | Medium | Project team / maintainer | Future intraday data and execution governance | v1 uses daily OHLCV only. |

## Backlog: Out of Scope

| Backlog item | Status | Priority | Owner | Evidence / future deliverable | Notes |
| --- | --- | --- | --- | --- | --- |
| Live broker execution | Out of scope | Critical | Project team / maintainer | None for v1 | Out of v1; VSEF v1 does not execute trades. |
| Real BUY / SELL / HOLD advice | Out of scope | Critical | Project team / maintainer | None for v1 | Out of v1; outputs are diagnostic only. |
| Capital allocation engine | Out of scope | Critical | Project team / maintainer | None for v1 | Out of v1; do not present diagnostic candidates as allocations. |
| Reinforcement learning trading system | Out of scope | Medium | Project team / maintainer | None for v1 | Out of frozen v1 model registry. |

## Evidence Rules

A task is only "Done" if it has:

- A committed document or artifact
- Clear acceptance criteria
- Reviewable evidence path

For working-tree drafts, the evidence path may be present before commit, but
release sign-off should not treat the task as final until the document or
artifact is committed and reviewable in version control.

## Scope Control Rules

- New ideas must be added to a backlog table before they are implemented.
- Phase 0 must not contain implementation work.
- Backlog placement does not approve future implementation.
- v1.5/v2 candidates require separate approval, acceptance criteria, and
  artifact evidence.
- Existing code outside the frozen scope may remain in the repository, but it
  must not be described as frozen VSEF v1 scope without governance approval.

## Governance Change Request Rule

Any change to frozen VSEF v1 scope must be handled as a governance change
request before it is added to Phase 0, VSEF v1, or implementation planning. The
request must document:

- Proposed change
- Reason
- Affected documents
- Affected runtime surfaces
- Evidence required
- Approval status

The project tracker must classify the request as approved, deferred, blocked,
or out of scope before any implementation work begins.

## Acceptance Criteria

- [x] All Phase 0 tasks are listed.
- [x] Each task has owner, priority, status, evidence.
- [x] Backlog prevents scope creep.
- [x] No implementation task is added to Phase 0.

## Related Governance Documents

- [VSEF v1 Architecture Freeze](../architecture/VSEF_v1_ARCHITECTURE.md)
- [VSEF v1 Model Registry](MODEL_REGISTRY.md)
- [VSEF v1 Data Policy](DATA_POLICY.md)
- [VSEF v1 Evaluation Protocol](EVALUATION_PROTOCOL.md)
