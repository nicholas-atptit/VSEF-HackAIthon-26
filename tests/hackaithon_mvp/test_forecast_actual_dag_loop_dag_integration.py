from copy import deepcopy

from src.hackaithon_mvp.forecast_actual_dag_loop import attach_evaluation_to_dag_result


def _evaluation():
    return {
        "actual_data_status": "provided",
        "rows_total": 2,
        "eligible_directional_rows": 2,
        "abstained_rows": 0,
        "correct_directional_rows": 1,
        "incorrect_directional_rows": 1,
        "directional_accuracy": 0.5,
        "balanced_directional_accuracy": 0.5,
        "coverage_ratio": 1.0,
        "abstention_ratio": 0.0,
        "top_k_summary": {"top_k": 1, "selected_rows": 1},
    }


def test_attach_evaluation_to_dag_result_does_not_mutate_input():
    dag_result = {
        "run_id": "demo",
        "final_state": {"forecast_diagnostic": {"forecast_diagnostic": "positive_bias"}},
    }
    original = deepcopy(dag_result)

    updated = attach_evaluation_to_dag_result(dag_result, _evaluation())

    assert dag_result == original
    assert updated is not dag_result
    assert "forecast_actual_evaluation" not in dag_result


def test_attached_dag_result_includes_compact_evaluation_summary():
    updated = attach_evaluation_to_dag_result({"run_id": "demo", "final_state": {}}, _evaluation())

    assert updated["forecast_actual_evaluation"]["rows_total"] == 2
    assert updated["forecast_actual_evaluation"]["coverage_ratio"] == 1.0
    assert updated["final_state"]["actual_data_status"] == "provided"
    assert updated["final_state"]["directional_accuracy"] == 0.5
    assert updated["final_state"]["balanced_directional_accuracy"] == 0.5
    assert updated["final_state"]["coverage_ratio"] == 1.0
