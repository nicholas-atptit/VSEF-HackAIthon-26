from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain
from src.hackaithon_mvp.evidence_packet import build_evidence_packet


REQUIRED_FIELDS = {
    "packet_version",
    "run_id",
    "ticker",
    "timeframe",
    "timeframe_unit",
    "run_mode",
    "scope",
    "generated_at",
    "engine_universe_summary",
    "forecast_diagnostic_summary",
    "chain_summary",
    "risk_summary",
    "routing_summary",
    "human_review_required",
    "claim_boundary",
    "non_claim",
    "warnings",
    "lineage",
}


def _packet(timeframe="1 ngày"):
    chain_output = run_diagnostic_chain("VCB", sample_size=20, timeframe=timeframe)
    return build_evidence_packet(
        chain_output,
        run_metadata={"run_id": "unit-run", "generated_at": "2026-06-20T00:00:00+00:00"},
    )


def test_evidence_packet_builds_from_vcb_chain_output():
    packet = _packet()

    assert REQUIRED_FIELDS.issubset(packet)
    assert packet["run_id"] == "unit-run"
    assert packet["ticker"] == "VCB"
    assert packet["run_mode"] == "static_local_review"
    assert packet["scope"] == "Baseline ML-only diagnostic MVP for a banking stock-evaluation use case."


def test_evidence_packet_preserves_canonical_timeframe():
    packet = _packet("1 ngày")

    assert packet["timeframe"] == "1d"
    assert packet["timeframe_unit"] == "day"


def test_evidence_packet_always_requires_human_review():
    packet = _packet()

    assert packet["human_review_required"] is True
    assert packet["routing_summary"]["human_review_required"] is True


def test_evidence_packet_claim_boundary_states_disabled_runtime_behaviors():
    packet = _packet()

    for boundary in (
        "no live data",
        "no provider API calls",
        "no model training",
        "no model inference",
        "no benchmark rerun",
        "no action guidance",
        "no financial advice",
    ):
        assert boundary in packet["claim_boundary"]


def test_evidence_packet_is_compact_and_does_not_include_all_engine_specs():
    packet = _packet()

    serialized = str(packet)
    assert "engine_specs" not in serialized
    assert "engine_ids" not in serialized
    assert packet["engine_universe_summary"]["full_engine_catalog_included"] is False
    assert len(packet["lineage"]) == 9


def test_evidence_packet_includes_forecast_counts_and_final_route():
    packet = _packet()

    counts = packet["forecast_diagnostic_summary"]["counts"]
    assert set(counts) == {"positive", "negative", "neutral", "insufficient", "exploratory"}
    assert packet["routing_summary"]["route"] in {
        "route_candidate",
        "maintain_watchlist_review",
        "reject",
        "escalate",
        "evidence_insufficient",
        "exploratory_only",
    }
