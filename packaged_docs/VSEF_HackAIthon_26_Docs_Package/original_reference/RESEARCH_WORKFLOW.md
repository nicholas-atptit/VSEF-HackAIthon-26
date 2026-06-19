# Research Workflow

1. Write a protocol defining universe, local-data scope, frequency, horizon, timestamp split, metrics, baselines, and claim boundary.
2. Validate provider policy and local-cache coverage without fetching live data.
3. Build point-in-time-safe features from trailing or lagged inputs only.
4. Build targets, then assign strict splits using both feature and target timestamps.
5. Fit on train rows and select candidates using validation rows only.
6. Score locked candidates on final rows without selection, tuning, or relocking.
7. Compare against task-appropriate and same-target baselines.
8. Write forecast panels or research artifacts, result summaries, claim boundaries, and evidence-index updates.
9. Preserve generated evidence and record missing coverage rather than fabricating or silently replacing it.

## Reproduction Modes

- Ordinary validation uses the safe commands in `docs/usage/RUNBOOK.md`.
- Offline forecast-engine reproduction uses `--offline-historical-only`.
- Heavy Model Universe runners require a written protocol.
- QML is excluded from the HackAIthon MVP scope.
- Provider APIs, live-data fetches, and benchmark reruns are outside ordinary validation.

## Authority Boundary

Do not translate diagnostic metrics into trading, profitability, BUY/SELL, recommendation, investment-advice, live-deployment, production, daily T+1, or unsupported VN100 claims.

Large historical runners remain one-off orchestrators. New reusable logic belongs under `src/`, with focused tests, before a runner consumes it. Update documentation when schemas, contracts, or claim boundaries change.
