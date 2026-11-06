"""A streamed or awaited reply is counted when it finishes, not when it starts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hearth
from hearth.trace import TraceRecorder

_USAGE = {
    "prompt_tokens": 10,
    "completion_tokens": 2,
    "prompt_tokens_details": {"cached_tokens": 8},
}


def test_stream_is_counted_after_the_last_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))

    class ChatStream:
        def create(self, **kwargs: Any) -> Any:
            assert kwargs["stream"] is True

            def chunks() -> Any:
                yield SimpleNamespace(text="Hi")
                yield SimpleNamespace(usage=dict(_USAGE))

            return chunks()

    recorder = TraceRecorder(trace_dir=tmp_path)
    wrapped = hearth.wrap(ChatStream(), mode="observe", recorder=recorder)
    stream = wrapped.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
        stream=True,
        session_id="stream-1",
    )
    assert recorder.read_session("stream-1") == []
    texts = [chunk.text for chunk in stream if hasattr(chunk, "text")]
    assert texts == ["Hi"]
    usage = recorder.read_session("stream-1")[0]["usage"]
    assert usage["read"] == 8
    assert usage["uncached"] == 2
    assert usage["output"] == 2


def test_async_call_is_counted_after_await(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))

    class ChatAsync:
        async def create(self, **_kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(usage=dict(_USAGE))

    recorder = TraceRecorder(trace_dir=tmp_path)
    wrapped = hearth.wrap(ChatAsync(), mode="observe", recorder=recorder)

    async def run() -> SimpleNamespace:
        return await wrapped.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
            session_id="async-1",
        )

    result = asyncio.run(run())
    assert result.usage["prompt_tokens"] == 10
    usage = recorder.read_session("async-1")[0]["usage"]
    assert usage["read"] == 8
    assert usage["output"] == 2
