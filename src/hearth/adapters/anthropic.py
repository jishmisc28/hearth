"""Anthropic usage parser and adapter (INV-06)."""

from __future__ import annotations

from typing import Any

from hearth.adapters.base import NormalizedUsage


def parse_anthropic_usage(usage_obj: Any) -> NormalizedUsage:
    """Normalize Anthropic usage so read + write + uncached == input_tokens (INV-06)."""
    raw: dict[str, Any] = {}
    if hasattr(usage_obj, "model_dump"):
        raw = usage_obj.model_dump()
    elif isinstance(usage_obj, dict):
        raw = usage_obj
    else:
        raw = {k: getattr(usage_obj, k) for k in dir(usage_obj) if not k.startswith("_")}

    input_tokens = int(raw.get("input_tokens", 0) or 0)
    read = int(raw.get("cache_read_input_tokens", 0) or 0)
    write = int(raw.get("cache_creation_input_tokens", 0) or 0)
    output = int(raw.get("output_tokens", 0) or 0)

    uncached = max(0, input_tokens - read - write)

    return NormalizedUsage(
        read=read,
        write=write,
        uncached=uncached,
        output=output,
        total_input=input_tokens,
        raw=raw,
    )
