"""OpenTelemetry instrumentation for prompt caching spans (BUILD_HANDBOOK §4.1, D-10)."""

from __future__ import annotations

import importlib
from typing import Any

# Optional OTel imports via importlib to avoid hard dependencies in core
_trace_mod = None
_tracer = None

try:
    _trace_mod = importlib.import_module("opentelemetry.trace")
    _tracer = _trace_mod.get_tracer("hearth", "0.1.0a1")
except Exception:
    pass


def is_otel_available() -> bool:
    return _tracer is not None


def record_span(
    *,
    session_id: str,
    call_index: int,
    provider: str,
    model: str,
    mode: str,
    read_tokens: int,
    write_tokens: int,
    uncached_tokens: int,
    output_tokens: int,
    cost_usd: str,
    breaks_count: int,
) -> Any:
    """Create an OTel span with semantic GenAI cache attributes if OTel is installed."""
    if _tracer is None:
        return None

    span = _tracer.start_span(f"hearth.call.{call_index}")
    total_input = read_tokens + write_tokens + uncached_tokens

    # GenAI semantic conventions (D-10)
    span.set_attribute("gen_ai.system", provider)
    span.set_attribute("gen_ai.request.model", model)
    span.set_attribute("gen_ai.usage.input_tokens", total_input)
    span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
    span.set_attribute("gen_ai.usage.cache_read.input_tokens", read_tokens)
    span.set_attribute("gen_ai.usage.cache_write.input_tokens", write_tokens)

    # Hearth specific dimensions
    span.set_attribute("hearth.session_id", session_id)
    span.set_attribute("hearth.call_index", call_index)
    span.set_attribute("hearth.mode", mode)
    span.set_attribute("hearth.cost_usd", cost_usd)
    span.set_attribute("hearth.breaks_count", breaks_count)

    span.end()
    return span
