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


def test_second_turn_resends_the_clock_already_sent() -> None:
    """The next turn must repeat the exact clock Hearth already sent on that message."""
    from hearth.guard import PrefixGuard
    from hearth.layout import LayoutMemory, optimize_layout

    memory = LayoutMemory()
    guard = PrefixGuard(min_prefix_tokens=1, ttl_seconds=3600.0)
    first_system, first_messages, _ = optimize_layout(
        "Stay stable.\nCurrent time: 2026-11-02T08:00:00\nFollow the rules.",
        [{"role": "user", "content": "Turn 1"}],
        memory=memory,
    )
    guard.evaluate_call(
        curr_params={"model": "gemini-2.5-flash"},
        curr_tools=[],
        curr_system=first_system,
        curr_messages=first_messages,
        total_tokens=50,
        ts=100.0,
    )
    second_system, second_messages, changes = optimize_layout(
        "Stay stable.\nCurrent time: 2026-11-02T08:00:10\nFollow the rules.",
        [
            {"role": "user", "content": "Turn 1"},
            {"role": "assistant", "content": "Noted."},
            {"role": "user", "content": "Turn 2"},
        ],
        memory=memory,
    )
    event = guard.evaluate_call(
        curr_params={"model": "gemini-2.5-flash"},
        curr_tools=[],
        curr_system=second_system,
        curr_messages=second_messages,
        total_tokens=80,
        ts=110.0,
    )
    reported = PrefixGuard(min_prefix_tokens=1, ttl_seconds=3600.0)
    reported.evaluate_call(
        curr_params={"model": "gemini-2.5-flash"},
        curr_tools=[],
        curr_system=first_system,
        curr_messages=first_messages,
        total_tokens=50,
        ts=100.0,
    )
    reported_event = reported.evaluate_call(
        curr_params={"model": "gemini-2.5-flash"},
        curr_tools=[],
        curr_system=second_system,
        curr_messages=second_messages,
        total_tokens=80,
        ts=110.0,
        provider_read_tokens=0,
    )
    assert second_system == first_system
    assert "2026-11-02T08:00:00" not in second_system
    assert second_messages[0]["content"] == first_messages[0]["content"]
    assert "2026-11-02T08:00:00" in second_messages[0]["content"]
    assert "2026-11-02T08:00:10" in second_messages[-1]["content"]
    assert "2026-11-02T08:00:00" not in second_messages[-1]["content"]
    assert any(change.get("kind") == "volatile_retained" for change in changes)
    # Before the provider answers, a matching prefix is not a break.
    assert event is None
    # A reported read of zero on that same prefix is the provider's miss.
    assert reported_event is not None
    assert reported_event.cause == "provider_miss"
    assert reported_event.user_caused is False


def test_rewritten_history_does_not_keep_the_old_clock() -> None:
    from hearth.layout import LayoutMemory, optimize_layout

    memory = LayoutMemory()
    optimize_layout(
        "Stay stable.\nCurrent time: 2026-11-02T08:00:00",
        [{"role": "user", "content": "Original question."}],
        memory=memory,
    )
    _, messages, _ = optimize_layout(
        "Stay stable.\nCurrent time: 2026-11-02T08:00:10",
        [
            {"role": "user", "content": "A different question, rewritten in place."},
            {"role": "assistant", "content": "Noted."},
            {"role": "user", "content": "Continue."},
        ],
        memory=memory,
    )
    assert messages[0]["content"] == "A different question, rewritten in place."
    assert "2026-11-02T08:00:00" not in messages[0]["content"]


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


def test_wrap_optimize_repeats_the_clock_on_the_next_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))
    client = _Client()
    wrapped = hearth.wrap(client, mode="optimize")
    first = [
        {"role": "system", "content": "Rules.\nCurrent time: 2026-11-02T08:00:00"},
        {"role": "user", "content": "Turn 1"},
    ]
    second = [
        {"role": "system", "content": "Rules.\nCurrent time: 2026-11-02T08:00:10"},
        {"role": "user", "content": "Turn 1"},
        {"role": "assistant", "content": "Noted."},
        {"role": "user", "content": "Turn 2"},
    ]
    wrapped.chat.completions.create(
        model="openai.gpt-oss-120b-1:0", messages=first, session_id="clock"
    )
    wrapped.chat.completions.create(
        model="openai.gpt-oss-120b-1:0", messages=second, session_id="clock"
    )
    sent_first = client.chat.completions.sent[0]["messages"]
    sent_second = client.chat.completions.sent[1]["messages"]
    assert sent_second[1]["content"] == sent_first[1]["content"]
    assert "2026-11-02T08:00:00" in sent_second[1]["content"]
    assert "2026-11-02T08:00:10" in sent_second[-1]["content"]
    assert "2026-11-02T08:00:10" not in sent_second[0]["content"]


def test_stable_prefix_with_zero_read_is_a_provider_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))
    from hearth.trace import TraceRecorder

    class _Create:
        def create(self, **kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(usage={"prompt_tokens": 3000, "completion_tokens": 1})

    recorder = TraceRecorder(trace_dir=tmp_path)
    wrapped = hearth.wrap(_Create(), mode="safe", recorder=recorder)
    messages = [
        {"role": "system", "content": "Rule. " * 4000},
        {"role": "user", "content": "Continue."},
    ]
    wrapped.create(model="gemini-2.5-flash", messages=messages, session_id="stable")
    wrapped.create(model="gemini-2.5-flash", messages=messages, session_id="stable")
    second = recorder.read_session("stable")[1]
    causes = [item.get("cause") for item in second.get("breaks", [])]
    assert causes == ["provider_miss"]
    assert second["breaks"][0]["user_caused"] is False


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
