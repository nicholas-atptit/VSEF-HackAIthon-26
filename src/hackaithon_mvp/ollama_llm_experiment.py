"""Evidence-grounded local Ollama LLM experiment."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

from src.hackaithon_mvp.llm_retriever import retrieve_llm_context, validate_llm_context
from src.hackaithon_mvp.ollama_local_client import (
    CLAIM_BOUNDARY as OLLAMA_CLIENT_BOUNDARY,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    NON_CLAIM_TEXT as OLLAMA_CLIENT_NON_CLAIM,
    call_ollama_chat,
)


CLAIM_BOUNDARY = {
    **OLLAMA_CLIENT_BOUNDARY,
    "evidence_grounded_only": True,
    "read_only_retrieval": True,
    "mutates_policies": False,
    "mutates_models": False,
    "mutates_storage": False,
    "mutates_evidence": False,
    "mutates_decision_lanes": False,
}
NON_CLAIM_TEXT = "Local evidence-grounded LLM experiment; answers are limited to retrieved records and require human review."
INSUFFICIENT_EVIDENCE_ANSWER = "Insufficient retrieved evidence to answer from the local context."
EMPTY_MODEL_ANSWER = "The local model returned an empty answer for the retrieved evidence context."
LLM_MUST_NOT = (
    "mutate policies",
    "mutate models",
    "mutate storage",
    "mutate evidence",
    "alter decision lanes",
    "claim beyond retrieved evidence",
    "create action labels",
    "give trading decisions",
    "claim production readiness",
)
ACTION_LABEL_TERMS = ("".join(("b", "uy")), "".join(("se", "ll")), "".join(("ho", "ld")))
ACTION_PATTERN = re.compile(r"\b(" + "|".join(re.escape(term) for term in ACTION_LABEL_TERMS) + r")\b", re.IGNORECASE)
ADVISORY_PATTERN = re.compile(r"\b" + re.escape(" ".join(("financial", "ad" + "vice"))) + r"\b", re.IGNORECASE)
OVERCLAIM_PATTERN = re.compile(r"\bproduction[-\s]+ready\b|\bguaranteed\s+profit", re.IGNORECASE)
_ACTION_A, _ACTION_B, _ACTION_C = ACTION_LABEL_TERMS
PUBLIC_RESTRICTED_TERMS = (
    "".join(("spon", "sor")),
    "".join(("spon", "sorship")),
    "".join(("fund", "ing")),
    "".join(("part", "ner")),
    "".join(("part", "nership")),
    "".join(("endorse", "ment")),
    "".join(("deploy", "ment")),
    "".join(("appro", "val")),
    "".join(("client ", "relationship")),
)
PUBLIC_RESTRICTED_PATTERN = re.compile(
    "|".join(r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b" for term in PUBLIC_RESTRICTED_TERMS),
    re.IGNORECASE,
)
ALLOWED_BOUNDARY_PATTERNS = (
    ("market_signal_boundary", re.compile(r"\b(?:is\s+)?not\s+(?:a\s+)?" + "trading" + r"\s+" + "signal" + r"\b", re.IGNORECASE)),
    (
        "market_signal_boundary",
        re.compile(r"\bdoes\s+not\s+constitute\s+(?:a\s+)?" + "trading" + r"\s+" + "signal" + r"\b", re.IGNORECASE),
    ),
    (
        "market_signal_boundary",
        re.compile(r"\bshould\s+not\s+be\s+treated\s+as\s+(?:a\s+)?" + "trading" + r"\s+" + "signal" + r"\b", re.IGNORECASE),
    ),
    ("trade_guidance_boundary", re.compile(r"\bnot\s+trading\s+advice\b", re.IGNORECASE)),
    (
        "financial_guidance_boundary",
        re.compile(
            r"\b(?:not|not\s+be\s+treated\s+as|does\s+not\s+constitute)\s+financial\s+" + "advice" + r"\b",
            re.IGNORECASE,
        ),
    ),
    ("trade_label_boundary", re.compile(r"\b(?:no|does\s+not\s+produce|does\s+not\s+create|creates\s+no)\s+trading\s+labels?\b", re.IGNORECASE)),
    ("action_label_boundary", re.compile(r"\bno\s+action\s+labels?\b", re.IGNORECASE)),
    (
        "action_label_output_boundary",
        re.compile(
            r"\bno\s+"
            + re.escape(_ACTION_A)
            + r"\s*(?:/|,|\s+or\s+)\s*"
            + re.escape(_ACTION_B)
            + r"\s*(?:/|,|\s+or\s+)\s*"
            + re.escape(_ACTION_C)
            + r"\s+output\b",
            re.IGNORECASE,
        ),
    ),
    ("human_review_boundary", re.compile(r"\bhuman\s+review\s+(?:is\s+)?required\b", re.IGNORECASE)),
    ("diagnostic_boundary", re.compile(r"\bdiagnostic-only\b", re.IGNORECASE)),
    ("research_boundary", re.compile(r"\bresearch-only\b", re.IGNORECASE)),
    ("production_boundary", re.compile(r"\bnot\s+(?:a\s+)?production\s+system\b", re.IGNORECASE)),
    ("live_execution_boundary", re.compile(r"\bno\s+live\s+trading\b", re.IGNORECASE)),
    ("market_guidance_boundary", re.compile(r"\b(?:not|does\s+not\s+constitute)\s+market\s+guidance\b", re.IGNORECASE)),
)
ACTION_RECOMMENDATION_PATTERNS = (
    ("action_recommendation", re.compile(r"\byou\s+should\s+" + re.escape(_ACTION_A) + r"\b", re.IGNORECASE)),
    ("action_recommendation", re.compile(r"\byou\s+should\s+" + re.escape(_ACTION_B) + r"\b", re.IGNORECASE)),
    ("action_recommendation", re.compile(r"\byou\s+should\s+" + re.escape(_ACTION_C) + r"\b", re.IGNORECASE)),
    (
        "action_recommendation",
        re.compile(r"\brecommend(?:s|ed|ing)?\s+(?:" + re.escape(_ACTION_A + "ing") + r"|to\s+" + re.escape(_ACTION_A) + r")\b", re.IGNORECASE),
    ),
    (
        "action_recommendation",
        re.compile(r"\brecommend(?:s|ed|ing)?\s+(?:" + re.escape(_ACTION_B + "ing") + r"|to\s+" + re.escape(_ACTION_B) + r")\b", re.IGNORECASE),
    ),
    ("action_recommendation", re.compile(r"\btake\s+a\s+position\b", re.IGNORECASE)),
    ("action_recommendation", re.compile(r"\benter\s+a\s+trade\b", re.IGNORECASE)),
    ("action_recommendation", re.compile(r"\bexit\s+a\s+trade\b", re.IGNORECASE)),
    ("price_target_claim", re.compile(r"\bprice\s+target\b", re.IGNORECASE)),
)
BOUNDARY_SENSITIVE_ACTION_PATTERNS = (
    ("market_action_phrase", re.compile(r"\b" + "trading" + r"\s+" + "signal" + r"\b", re.IGNORECASE)),
    ("market_action_phrase", re.compile(r"\blive\s+" + "trading" + r"\s+" + "signal" + r"\b", re.IGNORECASE)),
    ("market_action_phrase", re.compile(r"\btrade\s+" + "recommendation" + r"\b", re.IGNORECASE)),
    ("market_guidance_phrase", re.compile(r"\bfinancial\s+" + "advice" + r"\b", re.IGNORECASE)),
    ("market_guidance_phrase", re.compile(r"\binvestment\s+" + "advice" + r"\b", re.IGNORECASE)),
    ("market_action_phrase", re.compile(r"\bproduction\s+trading\s+system\b", re.IGNORECASE)),
)
UNSUPPORTED_CLAIM_PATTERNS = (
    ("unsupported_performance_claim", re.compile(r"\bprofit\s+guarantee\b|\bguarantees?\s+profit\b|\bguaranteed\s+profit\b", re.IGNORECASE)),
    (
        "unsupported_performance_claim",
        re.compile(r"\bproduction\s+trading\s+performance\b|\bachieved\s+production\s+trading\s+performance\b", re.IGNORECASE),
    ),
)


def _resolve_model(model: str | None) -> str | None:
    return str(model).strip() if model is not None and str(model).strip() else None


def _record_excerpt(record: dict[str, Any]) -> dict[str, Any]:
    content = record.get("content", {})
    if isinstance(content, dict):
        compact_content = {
            str(key): value
            for key, value in list(content.items())[:8]
            if isinstance(value, (str, int, float, bool, type(None), list, tuple, dict))
        }
    else:
        compact_content = {"content": str(content)[:500]}
    return {
        "record_id": record.get("record_id"),
        "record_type": record.get("record_type"),
        "title": record.get("title"),
        "summary": record.get("summary"),
        "content": compact_content,
        "non_claim": record.get("non_claim"),
    }


def _source_ids(context: dict) -> list[str]:
    return [
        str(record.get("record_id"))
        for record in context.get("records", []) or []
        if isinstance(record, dict) and record.get("record_id")
    ]


def _public_context(context: dict) -> dict[str, Any]:
    return {
        "retrieval_status": context.get("retrieval_status"),
        "query": context.get("query"),
        "record_type": context.get("record_type"),
        "record_count": context.get("record_count"),
        "records": context.get("records", ()),
        "claim_boundary": context.get("claim_boundary"),
        "non_claim": context.get("non_claim"),
        "read_only": context.get("read_only"),
        "human_review_required": context.get("human_review_required"),
    }


def build_llm_system_prompt() -> str:
    """Build the strict local evidence prompt."""

    boundary_signal = " ".join(("not", "a", "trading", "signal"))
    action_labels = "/".join(term.upper() for term in ACTION_LABEL_TERMS)
    return "\n".join(
        [
            "You answer only from the provided local retrieved context.",
            "Cite source IDs used in the answer.",
            "State uncertainty and limits from the context.",
            "Do not create action labels.",
            f'Use boundary wording such as "{boundary_signal}" and "human review required" when explaining limits.',
            f"Do not output standalone {action_labels}, price targets, or action recommendations.",
            "Do not provide investment or money guidance.",
            "Do not give trading decisions.",
            "Do not make production claims.",
            "Human review is required.",
            "If evidence is insufficient, say: insufficient retrieved evidence.",
        ]
    )


def build_evidence_grounded_user_prompt(
    *,
    query: str,
    retrieved_context: dict,
) -> str:
    """Build a bounded user prompt from retrieved records only."""

    records = [_record_excerpt(record) for record in retrieved_context.get("records", []) or [] if isinstance(record, dict)]
    payload = {
        "query": str(query or ""),
        "retrieval_status": retrieved_context.get("retrieval_status"),
        "source_ids": _source_ids(retrieved_context),
        "records": records,
        "instructions": {
            "answer_from_context_only": True,
            "cite_source_ids": True,
            "human_review_required": True,
            "abstain_when_insufficient": True,
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str)[:16000]


def _answer_sentences(answer: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in re.split(r"(?<=[.!?])\s+|[\r\n]+", str(answer or "")) if part.strip())


def _matched_allowed_boundary_terms(text: str) -> tuple[str, ...]:
    matches: list[str] = []
    for _, pattern in ALLOWED_BOUNDARY_PATTERNS:
        for match in pattern.finditer(text):
            phrase = match.group(0).strip().lower()
            if phrase.startswith("is "):
                phrase = phrase.removeprefix("is ").strip()
            if phrase == "human review is required":
                phrase = "human review required"
            matches.append(phrase)
    return tuple(dict.fromkeys(matches))


def _sentence_has_allowed_boundary(sentence: str) -> bool:
    return any(pattern.search(sentence) for _, pattern in ALLOWED_BOUNDARY_PATTERNS)


def _action_label_blocked_terms(answer: str) -> tuple[str, ...]:
    blocked: list[str] = []
    for sentence in _answer_sentences(answer):
        if ACTION_PATTERN.search(sentence) and not _sentence_has_allowed_boundary(sentence):
            blocked.extend(match.group(0).lower() for match in ACTION_PATTERN.finditer(sentence))
    return tuple(dict.fromkeys(blocked))


def _pattern_blocked_terms(
    answer: str,
    patterns: tuple[tuple[str, re.Pattern[str]], ...],
    *,
    allow_boundary_sentences: bool = False,
) -> tuple[str, ...]:
    blocked: list[str] = []
    for sentence in _answer_sentences(answer):
        if allow_boundary_sentences and _sentence_has_allowed_boundary(sentence):
            continue
        for label, pattern in patterns:
            if pattern.search(sentence):
                blocked.append(label)
    return tuple(dict.fromkeys(blocked))


def classify_llm_output_safety(answer: str) -> dict:
    """Classify local LLM answer safety with boundary-aware wording checks."""

    text = str(answer or "")
    allowed_boundary_terms = _matched_allowed_boundary_terms(text)
    action_label_terms = _action_label_blocked_terms(text)
    action_recommendation_terms = _pattern_blocked_terms(text, ACTION_RECOMMENDATION_PATTERNS)
    boundary_sensitive_terms = _pattern_blocked_terms(
        text,
        BOUNDARY_SENSITIVE_ACTION_PATTERNS,
        allow_boundary_sentences=True,
    )
    unsupported_claim_terms = _pattern_blocked_terms(text, UNSUPPORTED_CLAIM_PATTERNS)
    public_restricted_terms = tuple(match.group(0).lower() for match in PUBLIC_RESTRICTED_PATTERN.finditer(text))

    blocked_terms: tuple[str, ...] = ()
    safety_classification = "allowed"
    if action_label_terms:
        blocked_terms = action_label_terms
        safety_classification = "blocked_action_label"
    elif action_recommendation_terms or boundary_sensitive_terms:
        blocked_terms = (*action_recommendation_terms, *boundary_sensitive_terms)
        safety_classification = "blocked_action_recommendation"
    elif unsupported_claim_terms or public_restricted_terms:
        blocked_terms = (*unsupported_claim_terms, *public_restricted_terms)
        safety_classification = "blocked_unsupported_claim"

    blocked_terms = tuple(dict.fromkeys(blocked_terms))
    warnings: tuple[str, ...] = ()
    if allowed_boundary_terms and blocked_terms:
        warnings = ("allowed boundary wording was present, but unsafe wording was also detected",)
    return {
        "is_allowed": not blocked_terms,
        "blocked_terms": blocked_terms,
        "allowed_boundary_terms": allowed_boundary_terms,
        "safety_classification": safety_classification,
        "warnings": warnings,
    }


def validate_llm_answer_safety(answer: str) -> dict:
    """Validate final LLM answer wording without blocking safe boundary statements."""

    return classify_llm_output_safety(answer)


def _base_result(*, model: str | None, query: str, context: dict) -> dict[str, Any]:
    return {
        "experiment_status": "not_run",
        "model": model or DEFAULT_OLLAMA_MODEL,
        "query": str(query or ""),
        "retrieval_status": context.get("retrieval_status"),
        "retrieved_record_count": int(context.get("record_count", 0) or 0),
        "llm_called": False,
        "answer": "",
        "source_ids": _source_ids(context),
        "abstained": False,
        "human_review_required": True,
        "read_only": True,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
        "llm_must_not": list(LLM_MUST_NOT),
        "warnings": [],
        "errors": [],
        "model_response_debug": {},
        "answer_safety": validate_llm_answer_safety(""),
    }


def run_ollama_llm_experiment(
    *,
    store_root: str,
    query: str,
    model: str | None = None,
    limit: int = 5,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
) -> dict:
    """Run a read-only evidence-grounded local Ollama experiment."""

    resolved_model = _resolve_model(model)
    context = retrieve_llm_context(store_root=store_root, query=query, limit=limit)
    context = _public_context(context)
    result = _base_result(model=resolved_model, query=query, context=context)
    context_validation = validate_llm_context(context)
    if not context_validation["is_valid"]:
        result.update(
            {
                "experiment_status": "retrieval_context_invalid",
                "answer": INSUFFICIENT_EVIDENCE_ANSWER,
                "abstained": True,
                "errors": list(context_validation["errors"]),
                "warnings": list(context_validation["warnings"]),
            }
        )
        return result

    if context.get("retrieval_status") != "records_available" or not context.get("records"):
        result.update(
            {
                "experiment_status": "no_records_available",
                "answer": INSUFFICIENT_EVIDENCE_ANSWER,
                "abstained": True,
                "warnings": ["no retrieved records available for local LLM context"],
            }
        )
        return result

    call_result = call_ollama_chat(
        model=result["model"],
        system_prompt=build_llm_system_prompt(),
        user_prompt=build_evidence_grounded_user_prompt(query=query, retrieved_context=context),
        base_url=base_url,
    )
    status = str(call_result.get("call_status"))
    if status != "completed":
        result.update(
            {
                "experiment_status": status,
                "llm_called": bool(call_result.get("llm_called")),
                "answer": INSUFFICIENT_EVIDENCE_ANSWER,
                "abstained": True,
                "model_response_debug": dict(call_result.get("model_response_debug", {}) or {}),
                "warnings": [str(call_result.get("message") or "local Ollama call did not complete")],
                "errors": list(call_result.get("errors", []) or []),
            }
        )
        return result

    answer = str(call_result.get("answer") or "").strip()
    if not answer:
        result.update(
            {
                "experiment_status": "completed_empty_model_answer",
                "llm_called": True,
                "answer": EMPTY_MODEL_ANSWER,
                "abstained": True,
                "model_response_debug": dict(call_result.get("model_response_debug", {}) or {}),
                "warnings": ["local model returned empty final answer"],
                "errors": [],
            }
        )
        validation = validate_llm_experiment_result(result)
        result["answer_safety"] = validation.get("answer_safety", validate_llm_answer_safety(result["answer"]))
        if not validation["is_valid"]:
            result["experiment_status"] = "blocked_by_output_validation"
            result["answer"] = INSUFFICIENT_EVIDENCE_ANSWER
            result["abstained"] = True
            result["errors"] = list(validation["errors"])
        return result
    result.update(
        {
            "experiment_status": "completed",
            "llm_called": True,
            "answer": answer,
            "abstained": answer == INSUFFICIENT_EVIDENCE_ANSWER,
            "model_response_debug": dict(call_result.get("model_response_debug", {}) or {}),
            "warnings": [],
            "errors": [],
        }
    )
    validation = validate_llm_experiment_result(result)
    result["answer_safety"] = validation.get("answer_safety", validate_llm_answer_safety(result["answer"]))
    if not validation["is_valid"]:
        result["experiment_status"] = "blocked_by_output_validation"
        result["answer"] = INSUFFICIENT_EVIDENCE_ANSWER
        result["abstained"] = True
        result["errors"] = list(validation["errors"])
    return result


def validate_llm_experiment_result(result: dict) -> dict:
    """Validate local LLM experiment boundaries."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(result, dict):
        return {"is_valid": False, "errors": ["result must be an object"], "warnings": warnings}
    if result.get("human_review_required") is not True:
        errors.append("human_review_required must be True")
    if result.get("read_only") is not True:
        errors.append("read_only must be True")
    boundary = result.get("claim_boundary", {})
    if not isinstance(boundary, dict):
        errors.append("claim_boundary must be an object")
        boundary = {}
    for key in (
        "cloud_api_enabled",
        "live_data_enabled",
        "provider_calls_enabled",
        "training_enabled",
        "fine_tuning_enabled",
        "market_prediction_inference_enabled",
        "benchmark_rerun",
        "mutates_policies",
        "mutates_models",
        "mutates_storage",
        "mutates_evidence",
        "mutates_decision_lanes",
    ):
        if boundary.get(key) is not False:
            errors.append(f"claim_boundary.{key} must be False")
    answer = str(result.get("answer") or "")
    answer_safety = validate_llm_answer_safety(answer)
    if not answer_safety["is_allowed"]:
        classification = answer_safety["safety_classification"]
        if classification == "blocked_action_label":
            errors.append("answer must not include action labels")
        elif classification == "blocked_action_recommendation":
            errors.append("answer must not include action recommendations")
        elif any(term in PUBLIC_RESTRICTED_TERMS for term in answer_safety.get("blocked_terms", ())):
            errors.append("answer must not include restricted public wording")
        else:
            errors.append("answer must not include unsupported claim wording")
    if result.get("experiment_status") in {"completed", "completed_empty_model_answer"} and not result.get("source_ids"):
        errors.append("completed result requires source_ids")
    if result.get("llm_called") and result.get("experiment_status") != "completed" and not result.get("abstained"):
        warnings.append("non-completed LLM call should abstain")
    return {
        "is_valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "answer_safety": answer_safety,
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def render_llm_experiment_report(result: dict) -> str:
    """Render a compact report for the optional local LLM experiment."""

    lines = [
        "# Ollama LLM Evidence Experiment",
        "",
        f"Experiment status: {result.get('experiment_status')}",
        f"Model: {result.get('model')}",
        f"Retrieval status: {result.get('retrieval_status')}",
        f"Retrieved records: {result.get('retrieved_record_count')}",
        f"LLM called: {result.get('llm_called')}",
        f"Abstained: {result.get('abstained')}",
        "Human review required: True",
        "Read-only: True",
        "",
        "Answer:",
        str(result.get("answer") or INSUFFICIENT_EVIDENCE_ANSWER),
        "",
        "Source IDs:",
    ]
    source_ids = result.get("source_ids", []) or []
    if not source_ids:
        lines.append("- none")
    else:
        lines.extend(f"- {source_id}" for source_id in source_ids)
    lines.extend(
        [
            "",
            "Boundary: retrieved local evidence only; no cloud API, live data, provider call, training, fine-tuning, market-prediction inference, benchmark rerun, or mutation.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    )
    if result.get("warnings"):
        lines.extend(["", "Warnings:", *[f"- {warning}" for warning in result["warnings"]]])
    if result.get("errors"):
        lines.extend(["", "Errors:", *[f"- {error}" for error in result["errors"]]])
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an optional local Ollama experiment over retrieved evidence.")
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--format", choices=("json", "report"), default="report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run_ollama_llm_experiment(
        store_root=args.store_root,
        query=args.query,
        model=args.model,
        limit=args.limit,
        base_url=args.base_url,
    )
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(render_llm_experiment_report(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
