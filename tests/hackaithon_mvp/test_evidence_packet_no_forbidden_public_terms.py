import json
import re

from src.hackaithon_mvp.diagnostic_chain.diagnostic_chain_orchestrator import run_diagnostic_chain
from src.hackaithon_mvp.diagnostic_report import render_diagnostic_report
from src.hackaithon_mvp.evidence_packet import build_evidence_packet


FORBIDDEN_PATTERNS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\brecommendation\b",
    r"\btrading signal\b",
    r"\binvestment advice\b",
    r"\bportfolio allocation advice\b",
    r"\bsponsor(?:ship)?\b",
    r"\bfunding\b",
    r"\bpartnership\b",
    r"\bendorsement\b",
    r"\bclient relationship\b",
    r"\bdeployed for\b",
    r"\bapproved by\b",
)


def _assert_no_forbidden_terms(text: str) -> None:
    lowered = text.lower()
    for pattern in FORBIDDEN_PATTERNS:
        assert re.search(pattern, lowered) is None, pattern


def test_evidence_packet_output_has_no_forbidden_public_terms():
    chain_output = run_diagnostic_chain("VCB", sample_size=20, timeframe="1 ngày")
    packet = build_evidence_packet(chain_output, run_metadata={"run_id": "unit-run"})

    _assert_no_forbidden_terms(json.dumps(packet, sort_keys=True))


def test_diagnostic_report_output_has_no_forbidden_public_terms():
    chain_output = run_diagnostic_chain("VCB", sample_size=20, timeframe="1 ngày")
    packet = build_evidence_packet(chain_output, run_metadata={"run_id": "unit-run"})
    report = render_diagnostic_report(packet)

    _assert_no_forbidden_terms(report)
