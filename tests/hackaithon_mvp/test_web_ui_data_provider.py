import json

from src.hackaithon_mvp.web_ui.data_provider import (
    REQUIRED_SUMMARY_SECTIONS,
    build_demo_stock_profile,
    build_module_statuses,
    build_proposal_ui_summary,
    validate_proposal_ui_summary,
)


def test_summary_builds_with_required_sections():
    summary = build_proposal_ui_summary()
    validation = validate_proposal_ui_summary(summary)

    assert validation["valid"] is True
    assert set(REQUIRED_SUMMARY_SECTIONS).issubset(summary)
    assert summary["product_status"]["local_only"] is True
    assert summary["product_status"]["live_data"] is False
    assert summary["product_status"]["provider_calls"] is False
    assert summary["product_status"]["trading_output"] is False
    assert summary["product_status"]["human_review_required"] is True


def test_summary_contains_core_proposal_evidence():
    summary = build_proposal_ui_summary()

    assert summary["engine_universe"]["generated_specs"] == 77850
    assert summary["engine_universe"]["static_only_sweep"]["failed"] == 0
    assert summary["forecast_accuracy_gate"]["current_broad_local_gate"]["release_status"] == (
        "forecast_release_blocked_below_60pct"
    )
    assert summary["forecast_accuracy_gate"]["data_expanded_attempt"]["status"] == (
        "forecast_release_blocked_insufficient_rows"
    )
    assert summary["classical_61pct_benchmark"]["final_accuracy_percent"] == 61.61
    assert summary["classical_61pct_benchmark"]["claim_status"] == "exact-scope only"
    assert summary["classical_61pct_benchmark"]["broad_claim_allowed"] is False


def test_summary_has_no_action_labels_or_overclaims():
    text = json.dumps(build_proposal_ui_summary(), sort_keys=True)

    for forbidden in ("BUY", "SELL", "HOLD", "production-ready", "production ready"):
        assert forbidden not in text
    assert "VSEF predicts stocks with 61" not in text
    assert "forecasts all stocks at 61" not in text
    assert "market-action recommendation" not in text.lower()


def test_placeholder_modules_are_labeled_local_demo_or_placeholder():
    summary = build_proposal_ui_summary()
    modules = build_module_statuses()
    social = summary["social_listening_placeholder"]
    rag = summary["rag_llm_placeholder"]

    assert social["demo_placeholder"] is True
    assert social["no_scraping"] is True
    assert social["no_live_api"] is True
    assert "placeholder" in json.dumps(social).lower()
    assert "static demo" in rag["status"]
    assert "no real LLM call" in rag["status"]
    assert modules["local_only"] is True
    assert modules["provider_calls"] is False


def test_demo_stock_profile_uses_review_language_only():
    profile = build_demo_stock_profile("VCB")
    text = json.dumps(profile, sort_keys=True)

    assert profile["ticker"] == "VCB"
    assert profile["company_name"] == "Vietcombank"
    assert "Evidence supports further review" in text
    assert "Blocked by claim gate" in text
    assert "Human review required" in text
    for forbidden in ("BUY", "SELL", "HOLD"):
        assert forbidden not in text
