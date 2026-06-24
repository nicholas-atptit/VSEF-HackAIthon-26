import json

from src.hackaithon_mvp.web_ui.data_provider import (
    REQUIRED_SUMMARY_SECTIONS,
    build_module_statuses,
    build_proposal_ui_summary,
    build_report_preview,
    build_terminal_command_response,
    build_ticker_terminal_profile,
    build_vn30_terminal_universe,
    validate_proposal_ui_summary,
)


def _blocked_action_words() -> tuple[str, str, str]:
    return ("B" + "UY", "S" + "ELL", "H" + "OLD")


def _blocked_overclaim_words() -> tuple[str, str, str]:
    return ("production" + "-ready", "production " + "ready", "target " + "price")


def _blocked_broad_claims() -> tuple[str, str]:
    return ("VSEF predicts stocks with " + "61", "forecasts all stocks at " + "61")


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


def test_vn30_universe_contains_exactly_30_cards_with_required_fields():
    universe = build_vn30_terminal_universe()

    assert universe["ticker_count"] == 30
    assert len(universe["cards"]) == 30
    assert universe["universe_source"] == "demo_universe"
    required_fields = {
        "ticker",
        "display_name",
        "sector",
        "group",
        "data_coverage_status",
        "diagnostic_status",
        "risk_status",
        "forecast_gate_status",
        "evidence_status",
        "review_status",
        "latest_local_evidence_timestamp",
        "sparkline",
        "badges",
    }
    for card in universe["cards"]:
        assert required_fields.issubset(card)
        assert len(card["badges"]) == 4
        assert card["forecast_gate_status"] == "Gate blocked"


def test_ticker_profile_command_and_report_preview_work():
    profile = build_ticker_terminal_profile("VCB")
    command = build_terminal_command_response("VCB DIAG")
    chart_command = build_terminal_command_response("VCB CHART")
    report = build_report_preview("VCB")

    assert profile["ticker"] == "VCB"
    assert profile["company"] == "Vietcombank"
    assert profile["forecast_diagnostic_summary"]["release_status"] == "forecast_release_blocked_below_60pct"
    assert profile["engine_evidence_summary"]["generated_specs"] == 77850
    assert "forecast_chart_status" in profile
    assert "horizon_comparison" in profile
    assert command["command_status"] == "completed"
    assert command["payload"]["ticker"] == "VCB"
    assert command["payload"]["mode"] == "DIAG"
    assert chart_command["payload"]["mode"] == "CHART"
    assert report["scope"] == "VCB"
    assert report["writes_files_by_default"] is False
    assert report["export_root_if_enabled"] == ".tmp_web_ui_demo"
    assert "forecast_chart_summary" in report


def test_summary_contains_core_terminal_evidence():
    summary = build_proposal_ui_summary()

    assert summary["terminal_universe"]["ticker_count"] == 30
    assert summary["engine_universe"]["generated_specs"] == 77850
    assert summary["engine_universe"]["baseline_specs"] == 32850
    assert summary["engine_universe"]["auxiliary_specs"] == 22500
    assert summary["engine_universe"]["stack_specs"] == 22500
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

    for forbidden in (*_blocked_action_words(), *_blocked_overclaim_words()):
        assert forbidden not in text
    for forbidden in _blocked_broad_claims():
        assert forbidden not in text
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
    assert "local demo placeholder" in rag["status"]
    assert "no real LLM call" in rag["status"]
    assert modules["local_only"] is True
    assert modules["provider_calls"] is False
