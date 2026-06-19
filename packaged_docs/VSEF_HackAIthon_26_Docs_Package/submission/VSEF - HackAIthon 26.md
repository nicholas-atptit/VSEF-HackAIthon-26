# VSEF — Vietcombank Stock Evaluation Framework

**Subtitle:** HackAIthon-facing stock-evaluation and diagnostic framework for a banking research/risk-review context

Stakeholder clarification: In this HackAIthon submission, Vietcombank is used as the product-facing banking evaluation context and competition-use-case subject. This does not imply Vietcombank sponsorship, deployment, approval, endorsement, or partnership. Separately, the underlying VSEF research project includes research support from the Risk Management Department — Viettel Global, which is preserved only as research attribution.

## 1. Title and Submission Summary

VSEF is presented for HackAIthon 2026 as the Vietcombank Stock Evaluation Framework: a governed, AI-assisted diagnostic framework for Vietnamese equity evaluation in a banking research and risk-review context.

The framework helps analysts review market signals, model diagnostics, baseline comparisons, uncertainty, and evidence boundaries before forming a human interpretation. It is designed to support disciplined review, not autonomous trading.

VSEF is research-only and diagnostic-only. It does not provide BUY or SELL recommendations, investment advice, broker execution, trading authority, live execution, production trading readiness, or profitability guarantees.

## 2. Problem Statement

Vietnamese stock evaluation is difficult because useful signals are often mixed with unstable or misleading market behavior.

Several practical issues make evidence review important:

- Low liquidity can make price changes less reliable and easier to distort.
- Noisy or incomplete data can weaken model confidence.
- Fragmented information across market, company, macro, and investor-behavior sources can hide important context.
- Regime shifts can cause patterns that worked in one period to fail in another.
- Retail-driven volatility can amplify short-term movement that is not supported by fundamentals.
- Large actors may distort price or volume signals through concentrated activity or block trades.

The problem is therefore not only whether a model can predict direction. The core banking-review problem is whether analysts can see what the data supports, where the model is uncertain, how it compares with simple baselines, and what claims are not allowed.

## 3. Target Users

Bank research analysts use VSEF to review directional diagnostics, price or return signals, baseline comparisons, and evidence packets before forming research interpretations.

Risk-management reviewers use VSEF to identify weak data coverage, unstable model behavior, overfit risk, class imbalance, volatility sensitivity, and outputs that should be rejected or escalated.

Investment committee support teams use VSEF as a structured briefing surface. The framework organizes evidence and limitations, while the committee or analyst process remains responsible for judgment.

Compliance and governance reviewers use VSEF to check that outputs stay inside the approved authority boundary: no recommendation, no execution, no investment advice, and no unsupported profitability claim.

Academic and research evaluators use VSEF to inspect validation design, reproducibility, benchmark comparison, and limitations in the Vietnamese market setting.

## 4. Proposed Solution

VSEF is a governed AI-assisted stock-evaluation framework for Vietnamese equities. It combines local historical market data, point-in-time feature construction, diagnostic models, baseline comparison, risk checks, and evidence packaging.

The proposed HackAIthon MVP focuses on a repeatable review process:

1. collect bounded local historical evidence;
2. validate data coverage and quality;
3. generate diagnostic signals and baseline comparisons;
4. expose uncertainty, disagreement, and risk warnings;
5. package evidence for human review;
6. apply claim-boundary controls before any output is used in a presentation or decision-support workflow.

The solution is intentionally conservative. A forecast is not a recommendation. A strong historical metric is not proof of profit. A model output must be interpreted through data scope, validation design, baseline comparison, and governance limits.

Social listening, RAG/LLM workspaces, and a broad 90-100 check diagnostic layer are treated as intended future governed modules unless separate implementation evidence is added. They are not claimed as completed HackAIthon MVP capabilities here.

## 5. Why AI Is Used

AI is useful because market signals can be weak, nonlinear, regime-dependent, and hard to inspect manually at scale. VSEF uses AI to make evidence review more systematic, not to replace analyst judgment.

| Component | Review need it supports |
| --- | --- |
| Directional forecasting diagnostics | Scenario awareness for a defined horizon and universe. |
| Return or price diagnostics | Checks whether model outputs behave better than simple references. |
| Range and interval diagnostics | Uncertainty review when point estimates are too narrow or unstable. |
| Ranking diagnostics | Watchlist prioritization without creating recommendation authority. |
| Model-universe benchmarking | Robustness review across model families, features, horizons, and thresholds. |
| Risk diagnostics | Warnings for data gaps, volatility, class imbalance, model instability, and overfit risk. |
| Evidence governance | Controls what can be claimed and what must remain exploratory. |

The AI layer is valuable when it makes uncertainty and failure modes visible. It is harmful if it creates false confidence, so VSEF gives significant weight to baselines, negative results, and limitations.

## 6. System Workflow

```text
local historical market data
-> data validation
-> point-in-time feature construction
-> diagnostic model outputs
-> baseline and benchmark comparison
-> risk and uncertainty review
-> evidence packet
-> human analyst review
-> governance decision
```

In plain language, VSEF first checks whether the data is usable, then creates features that avoid future-data leakage, then produces diagnostics and compares them with baselines. The system then flags uncertainty, risk, and claim boundaries before sending an evidence packet to a human reviewer.

The expected review outcome is not "buy this stock" or "sell this stock." Expected outcomes include accept as bounded research evidence, reject as weak evidence, escalate for senior review, request more data, or keep as exploratory only.

## 7. Diagnostic and Risk-Management Engine

The diagnostic and risk-management engine prevents model output from being treated as direct investment instruction.

It reviews:

- data coverage and stale-cache risk;
- ticker and date availability;
- baseline competitiveness;
- model agreement and disagreement;
- validation-to-final transfer risk;
- rolling or regime stability;
- class imbalance;
- volatility and low-liquidity sensitivity;
- potential overfit or post-hoc selection risk;
- whether a claim is allowed under governance policy.

Current repository evidence supports diagnostic and governance concepts such as model-health summaries, baseline comparisons, validation-only selection, overfit-risk audits, and claim-boundary files. These are review surfaces only. They do not authorize trading, allocation, execution, or advice.

## 8. Human-in-the-Loop Workflow

VSEF keeps the human reviewer responsible for interpretation.

The analyst reviews the evidence packet and checks:

- what universe, date range, horizon, and target the result covers;
- whether data coverage is strong enough;
- how the output compares with simple baselines;
- whether models agree or conflict;
- whether uncertainty is high;
- whether the result survived validation-only selection;
- whether claim-boundary files allow the statement being made.

The reviewer can then accept, reject, escalate, or request more evidence. The system does not make a final investment decision.

## 9. Evidence and Validation

Existing repository evidence supports VSEF as a research-feasible diagnostic framework. It should be read with exact scope because different tracks use different targets, horizons, universes, and validation policies.

Strongest bounded classical result retained for the submission:

- VN30 hourly absolute-direction classical champion: 61.61% final accuracy, +10.90 percentage-point lift, 4,074 rows.
- Scope: VN30 hourly `absolute_direction`, L2 Logistic, `feature_set_C_closest`, h40.
- Interpretation: bounded offline research evidence, not trading performance and not a profitability claim.

Additional full-VN30 feasibility evidence:

- The recovered model-universe benchmark covers all 30 frozen January 2025 VN30 constituents.
- It planned 75 model variants and 1,868 evaluation cells; 74 variants and 1,864 cells ran successfully.
- The current-main full-coverage h40 Logistic L2 reference reports 61.6347569956% directional accuracy under validation-only selection and final scoring-only rules.
- This 61.63% result is not an average across all methods.
- The best post-hoc final row reached 63.33%, but it is descriptive only and not claim-eligible as a replacement.

QML is excluded from the HackAIthon MVP scope.

## 10. Limitations and Non-Claims

VSEF does not provide:

- BUY, SELL, or HOLD recommendations;
- investment advice;
- broker execution;
- live execution;
- trading authority;
- production trading readiness;
- profitability guarantees;
- market-beating guarantees;
- autonomous investment decisions.

Important limitations include:

- offline historical/local-data-first operation;
- possible stale cache or provider limitations;
- data gaps by ticker, date, source, or frequency;
- noisy short-horizon labels;
- low-liquidity sensitivity;
- regime shifts;
- retail-driven volatility;
- potential price or volume distortion by large actors;
- overfitting risk;
- class imbalance;
- QML is excluded from the HackAIthon MVP scope.

VSEF can organize evidence and warnings. It cannot remove market uncertainty.

## 11. Research Attribution

Luong Minh Quan - Posts and Telecommunications Institute of Technology

Contact: [luongminhquan.working.research@gmail.com](mailto:luongminhquan.working.research@gmail.com)

Nguyen Nguyet Ha - National Economics University

Contact: [nghnguyetha.workspace@gmail.com](mailto:nghnguyetha.workspace@gmail.com)

The underlying VSEF research project includes collaboration with, and financial support from, the Risk Management Department - Viettel Global. This is research attribution only. It must not be read as Vietcombank sponsorship, approval, deployment, endorsement, or partnership.

Market data is connected and retrieved through Vnstock, a Python package for Vietnamese stock market analysis.

Vnstock by thinh-vu on GitHub. Copyright (c) 2022-2026.

## 12. Appendix

### Repository Structure

```text
src/        Reusable code for data, features, evaluation, forecasting, governance, and reporting
scripts/    Research runners, validation scripts, maintenance tools, and package builders
tests/      Unit, integration, data-contract, and governance tests
docs/       Architecture, usage, workflow, and governance documentation
reports/    Results, claims, protocols, generated evidence, and paper materials
configs/    Research, forecasting, data, and validation configuration
data/       Protected local/cache data
outputs/    Protected output artifacts
```

### Evidence References

| Evidence item | Repository path |
| --- | --- |
| Classical VN30 full tuning summary | `reports/results/VN30_FULL_MODEL_TUNING_V3_RESULT_SUMMARY.md` |
| Full-VN30 proposal feasibility summary | `reports/proposal_feasibility_evidence_pack/FEASIBILITY_EVIDENCE_SUMMARY.md` |
| Comprehensive model-universe audit | `reports/generated/vn30_model_universe_benchmark/audit_result.md` |
| Model-universe claim boundary | `reports/generated/vn30_model_universe_benchmark/model_universe_claim_boundary.md` |
| Active evidence index | `reports/_index/ACTIVE_EVIDENCE_INDEX.md` |

### Safe Validation Commands

```powershell
python scripts/check_repo_hygiene.py
python scripts/check_runtime_preflight.py
```

### Heavy Research Runners

Do not rerun heavy research experiments without a written protocol.

```powershell
python scripts/research/run_vn30_model_universe_direction_price_benchmark.py --help
```

### Development Rules

- Work in the HackAIthon repository for HackAIthon MVP changes.
- Do not fetch live data or call provider APIs without a written protocol.
- Do not rerun benchmarks without a written protocol.
- Do not tune or select on final-period rows.
- Do not delete active evidence.
- Do not use final-period leaderboard rows as claim-eligible replacements.
- Do not convert diagnostics into recommendations or trading instructions.
