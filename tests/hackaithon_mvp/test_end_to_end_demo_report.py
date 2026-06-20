from src.hackaithon_mvp.end_to_end_demo import render_end_to_end_demo_report, run_end_to_end_demo


def test_report_text_is_neutral_and_bounded():
    report = render_end_to_end_demo_report(run_end_to_end_demo())

    assert "Local-only diagnostic fixture" in report
    assert "Human review is required." in report
    assert "No operational decision is produced." in report
    assert "No live data, provider calls, model training, model inference, or benchmark rerun is performed." in report


def test_report_includes_compact_summary_fields():
    report = render_end_to_end_demo_report(run_end_to_end_demo())

    assert "Demo status: completed" in report
    assert "DAG status: completed_with_warnings" in report
    assert "Forecast rows: 1" in report
    assert "Bar rows: 2" in report
    assert "Actual outcome rows: 1" in report
    assert "Directional accuracy: 1.0" in report
