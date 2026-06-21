from src.hackaithon_mvp.diagram_coverage_matrix import (
    DIAGRAM_BLOCKS,
    build_diagram_coverage_matrix,
    render_diagram_coverage_report,
    summarize_diagram_coverage,
)


def test_coverage_matrix_includes_every_diagram_block():
    matrix = build_diagram_coverage_matrix()

    assert {row["diagram_block"] for row in matrix} == set(DIAGRAM_BLOCKS)
    assert len(matrix) == len(DIAGRAM_BLOCKS)


def test_coverage_matrix_separates_status_categories():
    matrix = build_diagram_coverage_matrix()
    statuses = {row["mvp_status"] for row in matrix}
    summary = summarize_diagram_coverage(matrix)

    assert {"implemented", "implemented_as_contract", "implemented_as_local_demo", "partial", "future"}.issubset(
        statuses
    )
    assert summary["coverage_status"] == "complete"
    assert summary["partial_count"] >= 1
    assert summary["future_count"] >= 1


def test_coverage_matrix_documents_level_2_contract_blocks():
    rows = {row["diagram_block"]: row for row in build_diagram_coverage_matrix()}

    assert rows["social_listening"]["mvp_status"] == "implemented_as_contract"
    assert rows["feedback_loop"]["mvp_status"] == "implemented_as_contract"
    assert rows["periodic_output"]["mvp_status"] == "implemented_as_contract"
    assert rows["dashboard_destination"]["mvp_status"] == "implemented_as_local_demo"
    assert "no web dashboard" in rows["dashboard_destination"]["current_boundary"].lower()


def test_coverage_report_renders_summary():
    report = render_diagram_coverage_report(build_diagram_coverage_matrix())

    assert "# Diagram-to-Code Coverage Matrix" in report
    assert "data_sources" in report
    assert "dashboard_destination" in report
    assert "Human review remains required." in report
