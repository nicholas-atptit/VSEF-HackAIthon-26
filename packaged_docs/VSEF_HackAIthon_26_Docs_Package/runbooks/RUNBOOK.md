# HackAIthon MVP Package Runbook

This package is documentation-only. Use it to review the HackAIthon MVP scope, model inventory, and static evidence boundary.

QML is excluded from the HackAIthon MVP scope.

Safe local checks for the repository are:

```powershell
python -m pytest tests/hackaithon_mvp -q
python scripts/check_repo_hygiene.py
python scripts/check_runtime_preflight.py
```

Do not use this package to run live data access, provider calls, model training, or benchmark reruns.
