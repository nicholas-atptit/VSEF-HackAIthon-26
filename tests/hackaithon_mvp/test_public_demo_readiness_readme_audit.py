from pathlib import Path

from src.hackaithon_mvp.public_demo_readiness import audit_public_claim_boundaries, audit_public_readme


def test_readme_audit_passes_on_current_readme():
    readme = Path("README.md").read_text(encoding="utf-8")
    audit = audit_public_readme(readme)

    assert audit["is_safe"] is True
    assert audit["errors"] == []
    assert audit["missing_required_phrases"] == []


def test_readme_has_no_stale_old_header():
    readme = Path("README.md").read_text(encoding="utf-8")
    audit = audit_public_readme(readme)

    assert "# VSEF HackAIthon 2026 MVP" not in readme
    assert audit["stale_markers"] == []


def test_claim_boundary_audit_detects_action_or_advice_wording():
    audit = audit_public_claim_boundaries("This diagnostic is a trading signal and financial advice.")

    assert audit["is_safe"] is False
    categories = {hit["category"] for hit in audit["forbidden_hits"]}
    assert "market_action" in categories
    assert "advice_claim" in categories


def test_readme_audit_detects_excluded_scope_label():
    audit = audit_public_readme(
        "research-only diagnostic-only baseline ml-only human-review required no data gateway no live data "
        "no provider api calls no model training no model inference no benchmark rerun no action-oriented output "
        "no production readiness claim no profitability guarantee python -m src.hackaithon_mvp.end_to_end_demo "
        "python -m pytest tests/hackaithon_mvp -q --basetemp .pytest-tmp 422 passed qml"
    )

    assert audit["is_safe"] is False
    assert audit["forbidden_hits"]
