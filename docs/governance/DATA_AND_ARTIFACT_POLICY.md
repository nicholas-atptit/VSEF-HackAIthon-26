# Data and Artifact Policy

Use local historical/cached data by default. Provider APIs and live data fetches
require a separate explicit protocol.

Protected roots include active project-review, Model Universe, range-lab,
forecast-engine, result, claim, protocol, raw/cache data, output, archive, and
paper-evidence paths. The machine-readable registry is in
`src/governance/artifact_policy.py`.

Rules:

- Do not delete protected evidence or raw/cache data.
- Do not silently drop scripts or artifacts.
- Use `git mv` for tracked moves and record every move/deletion in a migration
  manifest.
- Treat generated artifacts as evidence, not disposable build output.
- Do not change research results or claim wording during structural cleanup.
- Do not commit secrets, `.env`, virtual environments, or cache folders.

QML is excluded from the HackAIthon MVP scope.


