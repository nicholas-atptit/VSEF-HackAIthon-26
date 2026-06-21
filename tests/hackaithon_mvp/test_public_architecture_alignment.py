from src.hackaithon_mvp.public_architecture_alignment import (
    audit_architecture_alignment_claims,
    build_public_architecture_alignment,
    render_public_architecture_alignment_report,
)


def test_public_architecture_alignment_has_required_categories():
    summary = build_public_architecture_alignment()

    for category in (
        "implemented_now",
        "local_demo_only",
        "contract_only",
        "future_scope",
        "explicitly_excluded",
    ):
        assert summary[category]


def test_public_architecture_alignment_explicitly_excludes_out_of_scope_runtime():
    summary = build_public_architecture_alignment()
    excluded = set(summary["explicitly_excluded"])

    assert {
        "live_data",
        "provider_api_calls",
        "model_training",
        "model_inference",
        "benchmark_rerun",
        "server_database",
        "dashboard_web_app",
        "Data Gateway",
        "operational_decisions",
    }.issubset(excluded)
    assert audit_architecture_alignment_claims(summary)["is_safe"] is True


def test_public_architecture_alignment_report_renders_boundaries():
    report = render_public_architecture_alignment_report(build_public_architecture_alignment())

    assert "# Public Architecture Alignment" in report
    assert "Local/static research MVP only." in report
    assert "Human review remains required." in report
