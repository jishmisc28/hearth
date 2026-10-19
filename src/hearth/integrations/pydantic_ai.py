"""Pydantic AI integration adapter for Hearth prompt caching (BUILD_HANDBOOK §6.1, M3)."""

from __future__ import annotations

from typing import Any

import hearth
from hearth.wrapper import WrappedClientProxy


def wrap_pydantic_ai_client(
    client: Any,
    mode: hearth.Mode = "safe",
    record: bool = False,
    strict: bool = False,
    recorder: hearth.TraceRecorder | None = None,
) -> Any:
    """Wrap an API client intended for Pydantic AI models.

    Usage:
        from pydantic_ai.models.anthropic import AnthropicModel
        from hearth.integrations.pydantic_ai import wrap_pydantic_ai_client

        wrapped = wrap_pydantic_ai_client(anthropic_client, mode="safe")
        model = AnthropicModel("model-name", anthropic_client=wrapped)
    """
    return hearth.wrap(client, mode=mode, record=record, strict=strict, recorder=recorder)


class HearthPydanticAIModel:
    """Proxy adapter wrapping a Pydantic AI model instance to enforce prompt cache stability."""

    def __init__(self, model: Any, mode: hearth.Mode = "safe"):
        self.underlying_model = model
        self.mode = mode
        # If model has client attribute, wrap it
        for attr in ("client", "_client", "anthropic_client", "openai_client"):
            if hasattr(model, attr):
                raw_c = getattr(model, attr)
                if not isinstance(raw_c, WrappedClientProxy):
                    setattr(model, attr, hearth.wrap(raw_c, mode=mode))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.underlying_model, name)
