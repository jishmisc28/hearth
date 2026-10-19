"""Mini-suite integration tests for LangGraph, Pydantic AI, and OpenAI Agents SDK (BUILD_HANDBOOK §10.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bench.tasks.registry import get_all_tasks
from hearth.integrations.langgraph import HearthMiddleware
from hearth.integrations.openai_agents import (
    get_default_openai_client,
    set_default_openai_client,
    wrap_agents_client,
)
from hearth.integrations.pydantic_ai import HearthPydanticAIModel, wrap_pydantic_ai_client
from hearth.trace import TraceRecorder


class MockModelClient:
    def __init__(self) -> None:
        self.call_count = 0
        self.last_kwargs: dict[str, Any] = {}

    def create(self, *args: Any, **kwargs: Any) -> Any:
        self.call_count += 1
        self.last_kwargs = kwargs

        class Resp:
            usage = {
                "prompt_tokens": 1500,
                "completion_tokens": 50,
                "prompt_tokens_details": {"cached_tokens": 1200},
            }

        return Resp()


def test_langgraph_middleware_mini_suite() -> None:
    """Verifies that LangGraph HearthMiddleware transforms state and preserves prefix stability."""
    tasks = get_all_tasks()[:3]
    middleware = HearthMiddleware(mode="optimize", session_id="langgraph-mini-test")

    for task in tasks:
        state = {
            "system": f"You are a coding agent for {task.title}.\nCurrent time: 2026-10-19T14:35:00Z\nDo task.",
            "messages": [
                {"role": "user", "content": task.user_query},
                {"role": "assistant", "content": "Working on it..."},
            ],
            "tools": task.tools,
        }

        # Step 1: Middleware processes graph node state
        transformed_state = middleware(state)

        # In optimize mode, volatile timestamp must be relocated out of system prompt
        assert "Current time:" not in transformed_state.get("system", "")
        # Relocated content must appear in messages
        msgs = transformed_state["messages"]
        assert any("Runtime Context:" in m["content"] for m in msgs)
        assert len(transformed_state.get("_hearth_changes", [])) > 0


def test_pydantic_ai_adapter_mini_suite(tmp_path: Path) -> None:
    """Verifies that Pydantic AI adapter wraps client and executes mini-suite."""
    tasks = get_all_tasks()[:3]
    recorder = TraceRecorder(trace_dir=tmp_path)

    for task in tasks:
        raw_client = MockModelClient()
        wrapped_client = wrap_pydantic_ai_client(raw_client, mode="safe", recorder=recorder)

        # Mock Pydantic AI Model structure
        class MockPydanticModel:
            def __init__(self, c: Any):
                self.client = c

        model = MockPydanticModel(wrapped_client)
        adapter = HearthPydanticAIModel(model, mode="safe")

        # Execute call
        resp = adapter.client.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": task.user_query}],
            session_id=f"pydantic-ai-{task.id}",
        )
        assert resp is not None
        assert raw_client.call_count == 1

        trace = recorder.read_session(f"pydantic-ai-{task.id}")
        assert len(trace) == 1
        assert trace[0]["usage"]["read"] == 1200


def test_openai_agents_sdk_adapter_mini_suite(tmp_path: Path) -> None:
    """Verifies that OpenAI Agents SDK adapter configures default client and executes mini-suite."""
    tasks = get_all_tasks()[:3]
    recorder = TraceRecorder(trace_dir=tmp_path)

    raw_client = MockModelClient()
    wrapped_client = wrap_agents_client(raw_client, mode="safe", recorder=recorder)
    set_default_openai_client(wrapped_client)

    active_client = get_default_openai_client()
    assert active_client is not None

    for task in tasks:
        resp = active_client.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": task.user_query}],
            session_id=f"agents-sdk-{task.id}",
        )
        assert resp is not None

    assert raw_client.call_count == 3
