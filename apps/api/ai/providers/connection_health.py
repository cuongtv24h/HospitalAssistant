"""Safe operational health checks for configured OpenAI-compatible LLMs."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import httpx


_DEFAULTS = {
    "gemini": {"model": "gemini-2.5-flash", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
    "openrouter": {"model": "google/gemini-2.5-flash", "base_url": "https://openrouter.ai/api/v1"},
    "groq": {"model": "llama-3.3-70b-versatile", "base_url": "https://api.groq.com/openai/v1"},
}
_LEGACY_KEYS = {
    "gemini": ("LLM_PRIMARY_API_KEY", "GEMINI_API_KEY"),
    "openrouter": ("LLM_FALLBACK_API_KEY", "OPENROUTER_API_KEY"),
    "groq": ("LLM_GROK_API_KEY", "GROQ_API_KEY"),
}


def _provider_order(env: Dict[str, str]) -> list[str]:
    value = env.get("LLM_PROVIDER_ORDER", "").strip()
    if value:
        return ["groq" if item.strip().lower() == "grok" else item.strip().lower() for item in value.split(",") if item.strip()]
    result = []
    for provider_id in _DEFAULTS:
        if _api_key(env, provider_id):
            result.append(provider_id)
    return result


def _api_key(env: Dict[str, str], provider_id: str) -> str:
    value = env.get("LLM_%s_API_KEY" % provider_id.upper(), "")
    if value:
        return value
    for key_name in _LEGACY_KEYS.get(provider_id, ()):
        if env.get(key_name):
            return env[key_name]
    return ""


def configured_llm_connections(environment: Optional[Dict[str, str]] = None) -> list[Dict[str, Any]]:
    """Return non-secret LLM configuration suitable for the admin dashboard."""
    env = environment if environment is not None else os.environ
    connections = []
    for position, provider_id in enumerate(_provider_order(env), start=1):
        defaults = _DEFAULTS.get(provider_id)
        if not defaults:
            connections.append({"provider": provider_id, "position": position, "status": "unsupported", "configured": False})
            continue
        prefix = "LLM_%s" % provider_id.upper()
        connections.append({
            "provider": provider_id,
            "position": position,
            "model": env.get(prefix + "_MODEL") or defaults["model"],
            "base_url": (env.get(prefix + "_BASE_URL") or defaults["base_url"]).rstrip("/"),
            "configured": bool(_api_key(env, provider_id)),
            "status": "configured" if _api_key(env, provider_id) else "missing_credentials",
        })
    return connections


def check_llm_connections(
    environment: Optional[Dict[str, str]] = None,
    client_factory: Callable[..., Any] = httpx.Client,
) -> Dict[str, Any]:
    """Probe each configured provider's non-generative models endpoint.

    API keys are only sent as authorization headers and are never returned,
    logged or included in an error message.
    """
    env = environment if environment is not None else os.environ
    results = configured_llm_connections(env)
    for result in results:
        provider_id = result["provider"]
        if result["status"] != "configured":
            continue
        started = time.monotonic()
        try:
            with client_factory(timeout=5.0) as client:
                response = client.get(
                    result["base_url"] + "/models",
                    headers={"Authorization": "Bearer " + _api_key(env, provider_id)},
                )
            result["latency_ms"] = round((time.monotonic() - started) * 1000)
            result["http_status"] = response.status_code
            result["status"] = "reachable" if 200 <= response.status_code < 300 else "authentication_failed" if response.status_code in {401, 403} else "unavailable"
        except (httpx.HTTPError, OSError, ValueError):
            result["latency_ms"] = round((time.monotonic() - started) * 1000)
            result["status"] = "unavailable"
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "connections": results}
