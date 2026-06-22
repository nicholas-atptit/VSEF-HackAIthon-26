import json
import subprocess
import sys

from src.hackaithon_mvp.engine_universe_gap_analysis import (
    render_engine_universe_gap_report,
    run_engine_universe_gap_analysis,
)


def test_engine_universe_gap_analysis_reports_latest_full_sweep_facts():
    result = run_engine_universe_gap_analysis()

    assert result["gap_status"] == "needs_evidence_before_stronger_claims"
    assert result["total_specs_discovered"] == 77_850
    assert result["total_specs_attempted"] == 77_850
    assert result["completed_count"] == 120
    assert result["skipped_count"] == 77_730
    assert result["failed_count"] == 0
    assert result["evidence_coverage_ratio"] == 0.001541
    assert result["diagnostic_distribution"]["insufficient_evidence"] == 77_730
    assert result["skip_reason_distribution"]["required dependency outputs unavailable"] == 45_000
    assert result["skip_reason_distribution"]["no matching static evidence for model target horizon"] == 32_730


def test_engine_universe_gap_analysis_explains_family_and_horizon_gaps():
    result = run_engine_universe_gap_analysis()

    assert result["family_distribution"]["ensemble_regime"] == 27_600
    assert result["family_distribution"]["classification"] == 19_050
    assert set(result["horizon_distribution"]) == {"1", "5", "10", "20", "40"}
    assert all(value == 15_570 for value in result["horizon_distribution"].values())
    assert "provide forecast_rows for common baseline specs" in result["coverage_priorities"]


def test_engine_universe_gap_report_renders_claim_boundary():
    report = render_engine_universe_gap_report(run_engine_universe_gap_analysis())

    assert "Engine Universe Gap Analysis" in report
    assert "Evidence coverage ratio: 0.001541" in report
    assert "77,850 is a generated diagnostic spec universe" in report


def test_engine_universe_gap_analysis_cli_report_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.engine_universe_gap_analysis", "--format", "report"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Completed specs: 120" in completed.stdout


def test_engine_universe_gap_analysis_cli_json_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-m", "src.hackaithon_mvp.engine_universe_gap_analysis"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["skipped_count"] == 77_730
