"""OpenAI-style chat messages keep the system text inside messages."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hearth
from hearth.adapters.openai import parse_openai_usage
from hearth.layout import optimize_chat_messages


def test_bedrock_usage_without_cache_fields_reconciles() -> None:
    usage = parse_openai_usage(
        {"completion_tokens": 8, "prompt_tokens": 1699, "total_tokens": 1707}
    )
    assert usage.read == 0
    assert usage.write == 0
    assert usage.uncached == 1699
    assert usage.read + usage.write + usage.uncached == usage.total_input


def test_optimize_chat_moves_clock_out_of_system_message() -> None:
    messages = [
        {
            "role": "system",
            "content": "Stay stable.\nCurrent time: 2026-11-02T09:00:00\nFollow the rules.",
        },
        {"role": "user", "content": "Say ok."},
    ]
    updated, changes = optimize_chat_messages(messages)
    assert "2026-11-02T09:00:00" not in updated[0]["content"]
    assert "Stay stable." in updated[0]["content"]
    assert "2026-11-02T09:00:00" in updated[-1]["content"]
    assert any(change.get("kind") == "volatile_relocated" for change in changes)


class ChatCompletions:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.sent.append(kwargs)
        return SimpleNamespace(usage={"prompt_tokens": 12, "completion_tokens": 1})


class _Chat:
    def __init__(self) -> None:
        self.completions = ChatCompletions()


class _Client:
    def __init__(self) -> None:
        self.chat = _Chat()


def test_wrap_optimize_rewrites_chat_system_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))
    client = _Client()
    wrapped = hearth.wrap(client, mode="optimize")
    messages = [
        {"role": "system", "content": "Rules.\nCurrent time: 2026-11-02T09:00:00"},
        {"role": "user", "content": "Say ok."},
    ]
    wrapped.chat.completions.create(model="openai.gpt-oss-120b-1:0", messages=messages)
    sent = client.chat.completions.sent[0]["messages"]
    assert "2026-11-02T09:00:00" not in sent[0]["content"]
    assert "2026-11-02T09:00:00" in sent[-1]["content"]


def test_wrap_observe_leaves_chat_messages_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))
    client = _Client()
    wrapped = hearth.wrap(client, mode="observe")
    messages = [
        {"role": "system", "content": "Rules.\nCurrent time: 2026-11-02T09:00:00"},
        {"role": "user", "content": "Say ok."},
    ]
    wrapped.chat.completions.create(model="openai.gpt-oss-120b-1:0", messages=messages)
    assert client.chat.completions.sent[0]["messages"] == messages
