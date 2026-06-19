# MVP Audit and Build Plan

## Current Repo Status

- Repository: `VSEF-HackAIthon-26`
- Purpose: dedicated HackAIthon 2026 MVP workspace derived from the VSEF research framework
- Branch for MVP preparation: `hackaithon-26-mvp`
- Remote URL: `https://github.com/nicholas-atptit/VSEF-HackAIthon-26.git`
- Source posture: research-only, diagnostic-only, offline historical/local-data-first unless explicitly revised later
- Existing research evidence: usable for bounded technical feasibility and diagnostic explanation only

## Stakeholder-Separation Risks

- Vietcombank must appear only as the HackAIthon product-facing banking/use-case context.
- Do not imply Vietcombank sponsorship, funding, approval, endorsement, deployment, or partnership.
- Viettel Global must remain only in the research attribution context for the underlying VSEF research work.
- Do not combine Vietcombank and Viettel Global into a single stakeholder, funder, sponsor, or deployment role.
- Avoid language that suggests institutional approval, production use, live operation, or advisory authority.

## MVP Objective

Prepare a reviewer-facing VSEF MVP that demonstrates a governed stock-evaluation and diagnostic workflow for a banking research/risk-review context. The MVP should show how analysts can inspect evidence, uncertainty, risk warnings, validation boundaries, and non-claims before making any human judgment.

The MVP is not a trading system. It is a diagnostic support and evidence-governance workspace.

## Minimum Viable Demo Workflow

1. Select a bounded Vietnamese stock-evaluation case.
2. Load or reference local historical evidence only.
3. Show data coverage and quality checks.
4. Present model or diagnostic outputs as research signals, not recommendations.
5. Compare outputs against simple baselines and validation evidence.
6. Display uncertainty, disagreement, overfit risk, and claim-boundary warnings.
7. Produce an evidence packet for human analyst review.
8. Require human accept/reject/escalate judgment before any downstream interpretation.

## Documents to Rewrite for Submission

- `VSEF - HackAIthon 26.md`: primary HackAIthon submission narrative.
- `HACKAITHON_26_WORKSPACE.md`: workspace authority and stakeholder-boundary note.
- `MVP_AUDIT_AND_BUILD_PLAN.md`: implementation and audit plan.
- `packaged_docs/VSEF_HackAIthon_26_Docs_Package/INDEX.md`: package index for submission/supporting review.
- Any future demo README or slide outline must preserve the same non-claims.

## Code Modules to Inspect

- `src/data/`: local data contracts, gateway assumptions, and coverage checks.
- `src/features/`: point-in-time feature construction and leakage controls.
- `src/evaluation/`: metric definitions, validation behavior, and benchmark comparisons.
- `src/forecasting/`: forecast diagnostics and model output surfaces.
- `src/governance/`: claim boundaries, policy checks, and diagnostic authority controls.
- `src/reporting/`: evidence packets, analysis cards, and reviewer-facing summaries.
- `scripts/`: safe validation scripts and MVP runner candidates.
- `tests/`: lightweight checks that can validate contracts without heavy research reruns.

## Safe Validation Commands

```powershell
git status --short
git diff --stat
git branch --show-current
git remote -v
python scripts/check_repo_hygiene.py
python scripts/check_runtime_preflight.py
```

Only run the Python checks if dependencies are available. Do not run heavy benchmarks, fetch live data, call provider APIs, or rerun model-universe experiments as part of MVP cleanup.

## Non-Claims and Risks

The MVP must not claim:

- BUY or SELL recommendation capability
- investment advice
- trading authority
- broker execution
- live execution
- profitability guarantee
- production trading readiness
- Vietcombank sponsorship, funding, approval, endorsement, deployment, or partnership

Remaining risks before implementation:

- Reviewer confusion between Vietcombank use-case framing and Viettel Global research attribution.
- Over-reading offline evidence as live trading performance.
- QML is excluded from the HackAIthon MVP scope.
- Treating post-hoc final-window leaderboard rows as claim-eligible.
- Presenting repository paths and benchmark details too heavily in the main submission narrative.

## Next Implementation Steps

1. Build a small reviewer-facing demo flow around existing local/offline evidence.
2. Add a clear evidence packet view with data scope, model scope, metric scope, and limitations.
3. Add governance labels that visibly separate diagnostics from recommendations.
4. Add or update light tests for any MVP presentation code.
5. Prepare a short demo script that explains the human-in-the-loop review outcome.
6. Keep active evidence files in place and package documentation copies only.
