"""Optional localhost-only Ollama client for bounded local experiments."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from typing import Any
from urllib import error, parse, request


DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_SECONDS = 30.0
ALLOWED_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
CLAIM_BOUNDARY = {
    "optional_local_experiment": True,
    "localhost_only": True,
    "cloud_api_enabled": False,
    "live_data_enabled": False,
    "provider_calls_enabled": False,
    "training_enabled": False,
    "fine_tuning_enabled": False,
    "market_prediction_inference_enabled": False,
    "benchmark_rerun": False,
    "auto_pull_enabled": False,
    "writes_files": False,
    "human_review_required": True,
}
NON_CLAIM_TEXT = "Optional local LLM experiment for retrieved diagnostic evidence; human review required."


def _resolve_model(model: str | None) -> str:
    value = str(model or "").strip() or str(os.environ.get("OLLAMA_MODEL", "")).strip()
    return value or DEFAULT_OLLAMA_MODEL


def _bounded_timeout(timeout_seconds: float) -> float:
    try:
        timeout = float(timeout_seconds)
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT_SECONDS
    return min(max(timeout, 0.1), 120.0)


def _normalize_base_url(base_url: str) -> tuple[str, str | None]:
    parsed = parse.urlparse(str(base_url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return "", "base_url must use http or https"
    host = parsed.hostname or ""
    if host not in ALLOWED_LOOPBACK_HOSTS:
        return "", "base_url must point to localhost"
    if parsed.scheme == "https":
        return "", "base_url must use local http"
    root = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    return root, None


def build_ollama_client_config(
    *,
    model: str | None = None,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Build a local-only Ollama client config."""

    resolved_base_url, error_text = _normalize_base_url(base_url)
    resolved_model = _resolve_model(model)
    return {
        "config_status": "invalid_base_url" if error_text else "ready",
        "model": resolved_model,
        "base_url": resolved_base_url or str(base_url or ""),
        "timeout_seconds": _bounded_timeout(timeout_seconds),
        "localhost_only": True,
        "auto_pull_enabled": False,
        "errors": [error_text] if error_text else [],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def _request_json(
    *,
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any] | None, str | None]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=_bounded_timeout(timeout_seconds)) as response:
            body = response.read()
    except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        return None, type(exc).__name__
    return _decode_ollama_response_body(body)


def _decode_ollama_response_body(body: bytes) -> tuple[dict[str, Any] | None, str | None]:
    """Decode Ollama JSON or accidental NDJSON stream payloads."""

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, f"invalid_json:{type(exc).__name__}"
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError as exc:
        chunks: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                return None, f"invalid_json:{type(exc).__name__}"
            if not isinstance(chunk, dict):
                return None, "invalid_json:stream_chunk_not_object"
            chunks.append(chunk)
        if chunks:
            return {"_stream_chunks": chunks}, None
        return None, f"invalid_json:{type(exc).__name__}"
    if not isinstance(decoded, dict):
        return None, "invalid_json:payload_not_object"
    return decoded, None


def _empty_response_debug(*, extraction_path: str = "not_called") -> dict[str, Any]:
    return {
        "raw_response_keys": [],
        "content_extraction_path": extraction_path,
        "thinking_present": False,
        "answer_length": 0,
    }


def _response_keys(payload: dict[str, Any]) -> list[str]:
    if "_stream_chunks" in payload and isinstance(payload.get("_stream_chunks"), list):
        keys: set[str] = set()
        for chunk in payload["_stream_chunks"]:
            if isinstance(chunk, dict):
                keys.update(str(key) for key in chunk.keys())
        return sorted(keys)
    return sorted(str(key) for key in payload.keys() if not str(key).startswith("_"))


def _extract_ollama_answer(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract final answer content without substituting model thinking."""

    raw_keys = _response_keys(payload)
    thinking_present = False
    answer = ""
    extraction_path = "empty"

    chunks = payload.get("_stream_chunks")
    if isinstance(chunks, list):
        message_parts: list[str] = []
        response_parts: list[str] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            message = chunk.get("message", {})
            if isinstance(message, dict):
                thinking_present = thinking_present or bool(message.get("thinking"))
                content = message.get("content")
                if content:
                    message_parts.append(str(content))
            thinking_present = thinking_present or bool(chunk.get("thinking"))
            response = chunk.get("response")
            if response:
                response_parts.append(str(response))
        if message_parts:
            answer = "".join(message_parts).strip()
            extraction_path = "stream.message.content"
        elif response_parts:
            answer = "".join(response_parts).strip()
            extraction_path = "stream.response"
        return answer, {
            "raw_response_keys": raw_keys,
            "content_extraction_path": extraction_path,
            "thinking_present": thinking_present,
            "answer_length": len(answer),
        }

    message = payload.get("message", {})
    if isinstance(message, dict):
        thinking_present = thinking_present or bool(message.get("thinking"))
        content = message.get("content")
        if content:
            answer = str(content).strip()
            extraction_path = "message.content"
    thinking_present = thinking_present or bool(payload.get("thinking"))
    if not answer and payload.get("response"):
        answer = str(payload["response"]).strip()
        extraction_path = "response"
    return answer, {
        "raw_response_keys": raw_keys,
        "content_extraction_path": extraction_path,
        "thinking_present": thinking_present,
        "answer_length": len(answer),
    }


def _compact_raw_response(payload: dict[str, Any], *, endpoint: str) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "done": payload.get("done"),
        "model": payload.get("model"),
        "created_at": payload.get("created_at"),
    }


def _available_model_names(tags_payload: dict[str, Any]) -> tuple[str, ...]:
    models = tags_payload.get("models", [])
    names: list[str] = []
    if isinstance(models, list):
        for item in models:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
            elif isinstance(item, str):
                names.append(item)
    return tuple(sorted(set(names)))


def check_ollama_availability(
    *,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    model: str | None = None,
) -> dict:
    """Check local Ollama and optional model availability."""

    config = build_ollama_client_config(model=model, base_url=base_url)
    if config["config_status"] != "ready":
        return {
            "availability_status": "invalid_base_url",
            "model": config["model"],
            "base_url": config["base_url"],
            "available_models": [],
            "message": "Ollama base URL must be a local HTTP loopback URL.",
            "errors": list(config["errors"]),
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    payload, request_error = _request_json(url=f"{config['base_url']}/api/tags", timeout_seconds=5.0)
    if request_error:
        return {
            "availability_status": "ollama_unavailable",
            "model": config["model"],
            "base_url": config["base_url"],
            "available_models": [],
            "message": "Local Ollama is unavailable. Start Ollama locally, run ollama list, and pass an installed model tag.",
            "errors": [request_error],
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    names = _available_model_names(payload or {})
    if config["model"] not in names:
        return {
            "availability_status": "model_unavailable",
            "model": config["model"],
            "base_url": config["base_url"],
            "available_models": list(names),
            "message": "Requested model is not installed locally. Run ollama list and pass an installed model tag.",
            "errors": [],
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    return {
        "availability_status": "available",
        "model": config["model"],
        "base_url": config["base_url"],
        "available_models": list(names),
        "message": "Local Ollama model is available.",
        "errors": [],
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_ollama_chat_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
) -> dict:
    """Build a bounded Ollama chat payload."""

    try:
        temp = float(temperature)
    except (TypeError, ValueError):
        temp = 0.1
    temp = max(0.0, min(temp, 1.0))
    return {
        "model": str(model),
        "stream": False,
        "think": False,
        "messages": [
            {"role": "system", "content": str(system_prompt or "")[:8000]},
            {"role": "user", "content": str(user_prompt or "")[:16000]},
        ],
        "options": {
            "temperature": temp,
            "num_predict": 512,
        },
    }


def _build_ollama_generate_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> dict:
    prompt = "\n\n".join(
        [
            f"System:\n{str(system_prompt or '')[:8000]}",
            f"User:\n{str(user_prompt or '')[:16000]}",
        ]
    )
    return {
        "model": str(model),
        "stream": False,
        "think": False,
        "prompt": prompt[:24000],
        "options": {
            "temperature": 0.1,
            "num_predict": 512,
        },
    }


def call_ollama_chat(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Call local Ollama chat after availability checks."""

    availability = check_ollama_availability(base_url=base_url, model=model)
    if availability["availability_status"] != "available":
        debug = _empty_response_debug(extraction_path="not_called")
        return {
            "call_status": availability["availability_status"],
            "model": availability["model"],
            "llm_called": False,
            "answer": "",
            "raw_response": {},
            "model_response_debug": dict(debug),
            **debug,
            "errors": list(availability.get("errors", [])),
            "message": availability.get("message"),
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    payload = build_ollama_chat_payload(
        model=availability["model"],
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    response_payload, request_error = _request_json(
        url=f"{availability['base_url']}/api/chat",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    if request_error:
        debug = _empty_response_debug(extraction_path="request_failed")
        return {
            "call_status": "ollama_unavailable",
            "model": availability["model"],
            "llm_called": False,
            "answer": "",
            "raw_response": {},
            "model_response_debug": dict(debug),
            **debug,
            "errors": [request_error],
            "message": "Local Ollama chat call failed cleanly.",
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    answer, debug = _extract_ollama_answer(response_payload)
    raw_response = _compact_raw_response(response_payload, endpoint="/api/chat")
    fallback_used = "none"
    if not answer:
        generate_payload = _build_ollama_generate_payload(
            model=availability["model"],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        generate_response, generate_error = _request_json(
            url=f"{availability['base_url']}/api/generate",
            method="POST",
            payload=generate_payload,
            timeout_seconds=timeout_seconds,
        )
        if generate_response is not None and not generate_error:
            generate_answer, generate_debug = _extract_ollama_answer(generate_response)
            fallback_used = "api_generate"
            if generate_answer:
                answer = generate_answer
                debug = generate_debug
                raw_response = _compact_raw_response(generate_response, endpoint="/api/generate")
            else:
                debug = {
                    **generate_debug,
                    "thinking_present": bool(debug.get("thinking_present")) or bool(generate_debug.get("thinking_present")),
                }
                raw_response = _compact_raw_response(generate_response, endpoint="/api/generate")
        else:
            debug = {
                **debug,
                "fallback_error": generate_error,
            }
    return {
        "call_status": "completed",
        "model": availability["model"],
        "llm_called": True,
        "answer": str(answer or "").strip(),
        "raw_response": raw_response,
        "model_response_debug": {
            **debug,
            "fallback_used": fallback_used,
        },
        "raw_response_keys": debug["raw_response_keys"],
        "content_extraction_path": debug["content_extraction_path"],
        "thinking_present": debug["thinking_present"],
        "answer_length": debug["answer_length"],
        "errors": [],
        "message": "Local Ollama chat completed.",
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "non_claim": NON_CLAIM_TEXT,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check optional localhost Ollama availability.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--format", choices=("json", "report"), default="json")
    return parser


def _render_check_report(result: dict) -> str:
    return "\n".join(
        [
            "# Local Ollama Client",
            "",
            f"Availability status: {result.get('availability_status')}",
            f"Model: {result.get('model')}",
            f"Base URL: {result.get('base_url')}",
            f"Available model count: {len(result.get('available_models', []) or [])}",
            str(result.get("message", "")),
            "",
            "Boundary: localhost-only optional experiment; no model pull, cloud API, live data, provider call, training, fine-tuning, market-prediction inference, or benchmark rerun.",
            str(result.get("non_claim", NON_CLAIM_TEXT)),
        ]
    ).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = check_ollama_availability(base_url=args.base_url, model=args.model)
    if args.format == "report":
        print(_render_check_report(result), end="")
    else:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
