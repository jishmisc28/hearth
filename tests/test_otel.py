"""Tests for OpenTelemetry span generation and GenAI semantic conventions (D-10)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import hearth


class MockResponse:
    def __init__(self, text: str = "ok"):
        self.text = text
        self.usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 800},
        }


class MockClient:
    def __init__(self) -> None:
        self.last_args: tuple[Any, ...] = ()
        self.last_kwargs: dict[str, Any] = {}

    def create(self, *args: Any, **kwargs: Any) -> MockResponse:
        self.last_args = args
        self.last_kwargs = kwargs
        return MockResponse()


def test_otel_span_emitted_on_wrapped_call() -> None:
    """Verifies that record_span is called with semantic cache attributes."""
    underlying = MockClient()
    client = hearth.wrap(underlying, mode="safe")

    with patch("hearth.wrapper.record_span") as mock_record:
        client.create(
            model="gemini-2.5-flash",
            messages=[{"role": "user", "content": "Hello OTel"}],
            session_id="otel-session-1",
        )

        assert mock_record.called
        kwargs = mock_record.call_args[1]
        assert kwargs["session_id"] == "otel-session-1"
        assert kwargs["provider"] == "gemini"
        assert kwargs["model"] == "gemini-2.5-flash"
        assert kwargs["mode"] == "safe"
        assert kwargs["read_tokens"] == 800
        assert kwargs["uncached_tokens"] == 200
