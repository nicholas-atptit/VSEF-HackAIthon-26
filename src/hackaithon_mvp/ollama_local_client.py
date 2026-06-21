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
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"invalid_json:{type(exc).__name__}"
    if not isinstance(decoded, dict):
        return None, "invalid_json:payload_not_object"
    return decoded, None


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
        "messages": [
            {"role": "system", "content": str(system_prompt or "")[:8000]},
            {"role": "user", "content": str(user_prompt or "")[:16000]},
        ],
        "options": {
            "temperature": temp,
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
        return {
            "call_status": availability["availability_status"],
            "model": availability["model"],
            "llm_called": False,
            "answer": "",
            "raw_response": {},
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
        return {
            "call_status": "ollama_unavailable",
            "model": availability["model"],
            "llm_called": False,
            "answer": "",
            "raw_response": {},
            "errors": [request_error],
            "message": "Local Ollama chat call failed cleanly.",
            "claim_boundary": dict(CLAIM_BOUNDARY),
            "non_claim": NON_CLAIM_TEXT,
        }

    message = response_payload.get("message", {}) if isinstance(response_payload, dict) else {}
    answer = message.get("content") if isinstance(message, dict) else None
    if answer is None:
        answer = response_payload.get("response", "") if isinstance(response_payload, dict) else ""
    return {
        "call_status": "completed",
        "model": availability["model"],
        "llm_called": True,
        "answer": str(answer or "").strip(),
        "raw_response": {
            "done": response_payload.get("done"),
            "model": response_payload.get("model"),
            "created_at": response_payload.get("created_at"),
        },
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
