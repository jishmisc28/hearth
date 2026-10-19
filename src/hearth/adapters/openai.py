"""OpenAI usage parser and adapter (INV-06)."""

from __future__ import annotations

from typing import Any

from hearth.adapters.base import NormalizedUsage


def parse_openai_usage(usage_obj: Any) -> NormalizedUsage:
    """Normalize OpenAI usage so read + write + uncached == prompt_tokens (INV-06)."""
    raw: dict[str, Any] = {}
    if hasattr(usage_obj, "model_dump"):
        raw = usage_obj.model_dump()
    elif isinstance(usage_obj, dict):
        raw = usage_obj
    else:
        raw = {k: getattr(usage_obj, k) for k in dir(usage_obj) if not k.startswith("_")}

    prompt_tokens = int(raw.get("prompt_tokens", 0) or 0)
    output = int(raw.get("completion_tokens", 0) or 0)

    # Read tokens from prompt_tokens_details.cached_tokens
    details = raw.get("prompt_tokens_details", {})
    if isinstance(details, dict):
        read = int(details.get("cached_tokens", 0) or 0)
    elif hasattr(details, "cached_tokens"):
        read = int(getattr(details, "cached_tokens", 0) or 0)
    else:
        read = 0

    write = int(raw.get("cache_write_tokens", 0) or 0)
    uncached = max(0, prompt_tokens - read - write)

    return NormalizedUsage(
        read=read,
        write=write,
        uncached=uncached,
        output=output,
        total_input=prompt_tokens,
        raw=raw,
    )
