"""Gemini usage parser and adapter (INV-06)."""

from __future__ import annotations

from typing import Any

from hearth.adapters.base import NormalizedUsage


def parse_gemini_usage(usage_obj: Any) -> NormalizedUsage:
    """Normalize Gemini usage so read + write + uncached == prompt_token_count (INV-06)."""
    raw: dict[str, Any] = {}
    if hasattr(usage_obj, "model_dump"):
        raw = usage_obj.model_dump()
    elif isinstance(usage_obj, dict):
        raw = usage_obj
    else:
        raw = {k: getattr(usage_obj, k) for k in dir(usage_obj) if not k.startswith("_")}

    prompt_tokens = int(raw.get("prompt_token_count", raw.get("promptTokenCount", 0)) or 0)
    read = int(raw.get("cached_content_token_count", raw.get("cachedContentTokenCount", 0)) or 0)
    output = int(raw.get("candidates_token_count", raw.get("candidatesTokenCount", 0)) or 0)

    write = 0
    uncached = max(0, prompt_tokens - read)

    return NormalizedUsage(
        read=read,
        write=write,
        uncached=uncached,
        output=output,
        total_input=prompt_tokens,
        raw=raw,
    )
