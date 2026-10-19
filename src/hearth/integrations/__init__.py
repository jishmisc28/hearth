"""Hearth framework integrations (Pydantic AI, OpenAI Agents SDK, LangGraph)."""

from __future__ import annotations

from hearth.integrations.langchain import HearthMiddleware as LangChainMiddleware
from hearth.integrations.langgraph import HearthMiddleware
from hearth.integrations.openai_agents import set_default_openai_client, wrap_agents_client
from hearth.integrations.pydantic_ai import HearthPydanticAIModel, wrap_pydantic_ai_client

__all__ = [
    "HearthMiddleware",
    "LangChainMiddleware",
    "wrap_pydantic_ai_client",
    "HearthPydanticAIModel",
    "set_default_openai_client",
    "wrap_agents_client",
]
