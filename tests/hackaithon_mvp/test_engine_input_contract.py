from copy import deepcopy

from src.hackaithon_mvp.engine_input_contract import (
    build_engine_input_contract,
    build_minimal_engine_input_fixture,
    validate_engine_input_payload,
)


def test_gateway_ready_input_contract_validates_good_payload():
    result = validate_engine_input_payload(build_minimal_engine_input_fixture(ticker="demo"))

    assert result["is_valid"] is True
    assert result["normalized_payload"]["request"]["ticker"] == "DEMO"
    assert result["normalized_payload"]["request"]["timeframe"] == "1d"
    assert result["claim_boundary"]["no_provider_calls"] is True


def test_invalid_payload_fails_safely():
    payload = build_minimal_engine_input_fixture()
    payload["request"]["horizon_steps"] = 0

    result = validate_engine_input_payload(payload)

    assert result["is_valid"] is False
    assert result["normalized_payload"] is None
    assert result["errors"]


def test_contract_rejects_secret_live_and_action_fields():
    payload = build_minimal_engine_input_fixture()
    payload["metadata"]["api_key"] = "hidden"
    payload["metadata"]["live_data"] = True
    payload["model_diagnostics"][0]["note"] = "".join(("B", "UY"))

    result = validate_engine_input_payload(payload)

    assert result["is_valid"] is False
    text = " ".join(result["errors"]).lower()
    assert "secret" in text
    assert "live-data" in text
    assert "action labels" in text


def test_forecast_rows_can_use_evaluator_schema():
    payload = build_minimal_engine_input_fixture()
    payload["forecast_rows"][0]["actual_future_return"] = 0.01
    payload["forecast_rows"][0]["actual_direction_label"] = "positive"

    result = validate_engine_input_payload(payload)

    assert result["is_valid"] is True
    assert result["normalized_payload"]["forecast_rows"][0]["actual_direction_label"] == "positive"


def test_contract_has_required_sections():
    contract = build_engine_input_contract()

    assert contract["contract_status"] == "gateway_ready_local_contract"
    assert "model_diagnostics" in contract["required_sections"]
    assert "social_context" in contract["required_sections"]
