"""Bedrock Converse reports a cache read as its own field, not inside prompt_tokens."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hearth
from hearth.adapters.bedrock import parse_bedrock_converse_usage
from hearth.bedrock_converse import BedrockConverse
from hearth.trace import TraceRecorder

# Captured 2026-11-02 from amazon.nova-micro-v1:0, two identical calls.
_WRITE = {
    "cacheReadInputTokenCount": 0,
    "cacheReadInputTokens": 0,
    "cacheWriteInputTokenCount": 2401,
    "cacheWriteInputTokens": 2401,
    "inputTokens": 6,
    "outputTokens": 2,
    "totalTokens": 2409,
}
_READ = {
    "cacheReadInputTokenCount": 2401,
    "cacheReadInputTokens": 2401,
    "cacheWriteInputTokenCount": 0,
    "cacheWriteInputTokens": 0,
    "inputTokens": 6,
    "outputTokens": 2,
    "totalTokens": 2409,
}


def test_converse_write_then_read_reconciles() -> None:
    first = parse_bedrock_converse_usage(_WRITE)
    second = parse_bedrock_converse_usage(_READ)
    assert (first.read, first.write, first.uncached, first.output) == (0, 2401, 6, 2)
    assert (second.read, second.write, second.uncached, second.output) == (2401, 0, 6, 2)
    for usage, raw in ((first, _WRITE), (second, _READ)):
        assert usage.read + usage.write + usage.uncached == usage.total_input
        assert usage.total_input + usage.output == raw["totalTokens"]


def test_converse_request_leaves_hearth_fields_out(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _Response:
        def read(self) -> bytes:
            return b'{"usage": {}}'

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    def _urlopen(request: urllib.request.Request, timeout: int = 0) -> _Response:
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode())
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    client = BedrockConverse("https://example.invalid", "test-key")
    client.create(
        model="amazon.nova-micro-v1:0",
        system=[{"text": "stable"}],
        messages=[{"role": "user", "content": [{"text": "ok"}]}],
        session_id="session-1",
        inferenceConfig={"maxTokens": 8, "temperature": 0},
    )
    assert captured["url"] == ("https://example.invalid/model/amazon.nova-micro-v1:0/converse")
    assert captured["body"]["system"] == [{"text": "stable"}]
    assert "session_id" not in captured["body"]
    assert "model" not in captured["body"]
    assert "test-key" not in json.dumps(captured["body"])


def test_optimize_keeps_the_cache_checkpoint_and_the_old_clock() -> None:
    from hearth.layout import LayoutMemory, optimize_converse_system

    memory = LayoutMemory()
    system = [
        {"text": "Rules.\nCurrent time: 2026-11-02T08:00:00"},
        {"cachePoint": {"type": "default"}},
    ]
    first_system, first_messages, _ = optimize_converse_system(
        system,
        [{"role": "user", "content": [{"text": "Turn 1"}]}],
        memory=memory,
    )
    assert first_system[1] == {"cachePoint": {"type": "default"}}
    assert "2026-11-02T08:00:00" not in first_system[0]["text"]
    assert "Rules." in first_system[0]["text"]
    assert "2026-11-02T08:00:00" in first_messages[0]["content"][1]["text"]

    second_system, second_messages, changes = optimize_converse_system(
        [
            {"text": "Rules.\nCurrent time: 2026-11-02T08:00:10"},
            {"cachePoint": {"type": "default"}},
        ],
        [
            {"role": "user", "content": [{"text": "Turn 1"}]},
            {"role": "assistant", "content": [{"text": "Noted."}]},
            {"role": "user", "content": [{"text": "Turn 2"}]},
        ],
        memory=memory,
    )
    assert second_system[1] == {"cachePoint": {"type": "default"}}
    assert second_messages[0]["content"] == first_messages[0]["content"]
    assert "2026-11-02T08:00:10" in second_messages[-1]["content"][-1]["text"]
    assert "2026-11-02T08:00:00" not in second_messages[-1]["content"][-1]["text"]
    assert any(change.get("kind") == "volatile_retained" for change in changes)


def test_wrap_records_a_converse_cache_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))

    class BedrockConverse:
        def create(self, **_kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(usage=dict(_READ))

    recorder = TraceRecorder(trace_dir=tmp_path)
    wrapped = hearth.wrap(BedrockConverse(), mode="observe", recorder=recorder)
    wrapped.create(
        model="amazon.nova-micro-v1:0",
        system=[{"text": "stable"}],
        messages=[],
        session_id="nova",
    )
    usage = recorder.read_session("nova")[0]["usage"]
    assert usage["read"] == 2401
    assert usage["write"] == 0
    assert usage["uncached"] == 6
