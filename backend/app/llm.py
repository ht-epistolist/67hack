"""Thin async wrapper around OpenRouter (OpenAI-compatible) for the agents.

Exposes a tool-calling chat turn and a structured-JSON helper. If no API key is
configured the wrapper reports `available = False`; agents then fall back to a
deterministic analysis path so the demo still runs end-to-end offline.
"""
from __future__ import annotations

import json
from typing import Any

from app.config import settings

try:
    from openai import AsyncOpenAI

    _client = (
        AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": "https://frtc.local",
                "X-Title": "frtc multi-agent fraud investigator",
            },
        )
        if settings.openrouter_api_key
        else None
    )
except Exception:  # pragma: no cover
    _client = None


def available() -> bool:
    return _client is not None


async def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 350,
):
    """One chat turn. Returns the raw assistant message (may carry tool_calls).

    `max_tokens` is capped low on purpose — agent messages should be terse notes,
    not paragraphs (keeps the live feed readable and runs fast/cheap)."""
    if _client is None:
        raise RuntimeError("LLM unavailable (no OPENROUTER_API_KEY)")
    kwargs: dict[str, Any] = {
        "model": model or settings.agent_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = await _client.chat.completions.create(**kwargs)
    return resp.choices[0].message


async def structured(
    system: str, user: str, schema_hint: str, model: str | None = None
) -> dict:
    """Ask for a single JSON object and parse it (best-effort)."""
    if _client is None:
        raise RuntimeError("LLM unavailable (no OPENROUTER_API_KEY)")
    resp = await _client.chat.completions.create(
        model=model or settings.reasoning_model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"{user}\n\nReturn ONLY valid JSON matching:\n{schema_hint}",
            },
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Strip markdown fences if the model wrapped the JSON.
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```")
        return json.loads(raw)
