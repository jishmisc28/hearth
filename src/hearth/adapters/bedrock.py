"""Amazon Bedrock Converse usage parser (INV-06).

Converse reports the cache read, the cache write, and the uncached tail as
separate counts. ``inputTokens`` is the uncached tail, not the whole prompt.
``totalTokens`` includes the output.
"""

from __future__ import annotations

from typing import Any

from hearth.adapters.base import NormalizedUsage


def _as_dict(usage_obj: Any) -> dict[str, Any]:
    if isinstance(usage_obj, dict):
        return usage_obj
    if hasattr(usage_obj, "model_dump"):
        dumped = usage_obj.model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {key: getattr(usage_obj, key) for key in dir(usage_obj) if not key.startswith("_")}


def _first_int(raw: dict[str, Any], *names: str) -> int:
    for name in names:
        if raw.get(name) is not None:
            return int(raw[name] or 0)
    return 0


def parse_bedrock_converse_usage(usage_obj: Any) -> NormalizedUsage:
    """Normalize a Converse usage object so read + write + uncached is the input total."""
    raw = _as_dict(usage_obj)
    read = _first_int(raw, "cacheReadInputTokens", "cacheReadInputTokenCount")
    write = _first_int(raw, "cacheWriteInputTokens", "cacheWriteInputTokenCount")
    uncached = _first_int(raw, "inputTokens")
    output = _first_int(raw, "outputTokens")
    return NormalizedUsage(
        read=read,
        write=write,
        uncached=uncached,
        output=output,
        total_input=read + write + uncached,
        raw=raw,
    )
