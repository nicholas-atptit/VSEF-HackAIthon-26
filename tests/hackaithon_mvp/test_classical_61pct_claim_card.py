from src.hackaithon_mvp.classical_61pct_claim_card import (
    build_classical_61pct_claim_card,
    render_classical_61pct_claim_card,
)


def _write_fixture(root):
    result = root / "reports" / "results" / "VN30_FULL_MODEL_TUNING_V3_RESULT_SUMMARY.md"
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(
        "# VN30 Full Model Tuning v3\n"
        "- Current claimable champion: L2 Logistic, feature_set_C_closest, h40, threshold 0.50, 61.61% final accuracy, +10.90 pp lift, 4,074 rows.\n"
        "Paper-safe wording: strict-replay L2 Logistic absolute_direction champion remains exact-scope only.\n",
        encoding="utf-8",
    )
    audit = root / "reports" / "generated" / "vn30_model_universe_benchmark" / "audit_result.md"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        "Current main result: Logistic L2 baseline_C_closest h40 validation-selected threshold 0.55 (61.63%).\n"
        "| current_main_logistic_l2_h40_threshold_0.55 | logistic_l2 | paper_reference_current_main | validation-selected | 0.6163475699558174 | yes | yes |\n"
        "| h40 main claim kept separate | yes |\n",
        encoding="utf-8",
    )
    boundary = root / "reports" / "generated" / "vn30_model_universe_benchmark" / "model_universe_claim_boundary.md"
    boundary.write_text(
        "Final-window scores are scoring-only and are not used for selection.\n"
        "No trading, profitability, investment recommendation, or live-deployment claim is made.\n"
        "No generalization beyond the reported VN30 evidence is claimed.\n",
        encoding="utf-8",
    )


def test_classical_61pct_claim_card_ready_for_exact_scope(tmp_path):
    _write_fixture(tmp_path)

    card = build_classical_61pct_claim_card(repo_root=str(tmp_path))

    assert card["claim_allowed"] is True
    assert card["claim_allowed_only_within_exact_scope"] is True
    assert card["broad_claim_allowed"] is False
    assert card["exact_scope"]["target"] == "absolute_direction"
    assert card["rows"] == 4074
    assert "not broad whole-MVP accuracy" in card["non_claims"]
    assert "not a QML result" in card["non_claims"]


def test_classical_61pct_claim_card_blocks_missing_source(tmp_path):
    card = build_classical_61pct_claim_card(repo_root=str(tmp_path))

    assert card["claim_allowed"] is False
    assert card["claim_card_status"] == "classical_61pct_claim_card_blocked"
    assert card["allowed_wording"] is None


def test_classical_61pct_claim_card_report(tmp_path):
    _write_fixture(tmp_path)
    report = render_classical_61pct_claim_card(build_classical_61pct_claim_card(repo_root=str(tmp_path)))

    assert "Classical 61.61% Claim Card" in report
    assert "Claim allowed: True" in report
    assert "bounded VN30 hourly absolute-direction benchmark" in report
