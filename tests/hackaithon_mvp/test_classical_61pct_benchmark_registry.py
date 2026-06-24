from pathlib import Path

from src.hackaithon_mvp.classical_61pct_benchmark_registry import (
    MISSING_STATUS,
    VALID_STATUS,
    load_classical_61pct_evidence,
    render_classical_61pct_benchmark_report,
    validate_classical_61pct_scope,
)


def _write_fixture(root: Path) -> None:
    result = root / "reports" / "results" / "VN30_FULL_MODEL_TUNING_V3_RESULT_SUMMARY.md"
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(
        "\n".join(
            [
                "# VN30 Full Model Tuning v3",
                "- Current claimable champion: L2 Logistic, feature_set_C_closest, h40, threshold 0.50, 61.61% final accuracy, +10.90 pp lift, 4,074 rows.",
                "Paper-safe wording: strict-replay L2 Logistic absolute_direction champion remains exact-scope only.",
            ]
        ),
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


def test_load_classical_61pct_evidence_from_fixture(tmp_path):
    _write_fixture(tmp_path)

    evidence = load_classical_61pct_evidence(repo_root=str(tmp_path))
    validation = validate_classical_61pct_scope(evidence)

    assert evidence["source_evidence_found"] is True
    assert evidence["final_accuracy_percent"] == 61.61
    assert evidence["final_accuracy_exact"] == 0.6163475699558174
    assert evidence["rows"] == 4074
    assert evidence["target"] == "absolute_direction"
    assert validation["validation_status"] == VALID_STATUS
    assert validation["claim_allowed_exact_scope"] is True
    assert validation["broad_claim_allowed"] is False


def test_load_classical_61pct_evidence_missing_source(tmp_path):
    evidence = load_classical_61pct_evidence(repo_root=str(tmp_path))
    validation = validate_classical_61pct_scope(evidence)

    assert evidence["registry_status"] == MISSING_STATUS
    assert evidence["source_evidence_found"] is False
    assert validation["valid"] is False


def test_current_repo_classical_61pct_evidence_validates():
    evidence = load_classical_61pct_evidence()
    validation = validate_classical_61pct_scope(evidence)

    assert evidence["evidence_path"] == "reports/results/VN30_FULL_MODEL_TUNING_V3_RESULT_SUMMARY.md"
    assert evidence["feature_set"] == "feature_set_C_closest"
    assert evidence["horizon"] == "h40"
    assert validation["valid"] is True


def test_render_classical_61pct_benchmark_report(tmp_path):
    _write_fixture(tmp_path)
    evidence = load_classical_61pct_evidence(repo_root=str(tmp_path))
    report = render_classical_61pct_benchmark_report({**evidence, "validation": validate_classical_61pct_scope(evidence)})

    assert "Classical 61.61% Benchmark Registry" in report
    assert "Exact-scope claim allowed: True" in report
