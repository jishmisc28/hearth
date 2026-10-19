"""OpenAI Agents SDK integration adapter for Hearth prompt caching (BUILD_HANDBOOK §6.1, M3)."""

from __future__ import annotations

from typing import Any

import hearth
from hearth.wrapper import WrappedClientProxy

_DEFAULT_AGENTS_CLIENT: Any = None


def set_default_openai_client(client: Any) -> None:
    """Set the default client for the OpenAI Agents SDK."""
    global _DEFAULT_AGENTS_CLIENT
    if not isinstance(client, WrappedClientProxy):
        _DEFAULT_AGENTS_CLIENT = hearth.wrap(client, mode="safe")
    else:
        _DEFAULT_AGENTS_CLIENT = client


def get_default_openai_client() -> Any:
    """Retrieve the configured default client for OpenAI Agents SDK."""
    return _DEFAULT_AGENTS_CLIENT


def wrap_agents_client(
    client: Any,
    mode: hearth.Mode = "safe",
    record: bool = False,
    strict: bool = False,
    recorder: hearth.TraceRecorder | None = None,
) -> Any:
    """Wrap an OpenAI or AsyncOpenAI client for the Agents SDK.

    Usage:
        from openai import OpenAI
        from hearth.integrations.openai_agents import wrap_agents_client

        wrapped = wrap_agents_client(OpenAI(), mode="safe")
    """
    return hearth.wrap(client, mode=mode, record=record, strict=strict, recorder=recorder)
