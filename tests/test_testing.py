"""Tests for FakeProvider mock client and cache simulation (BUILD_HANDBOOK §5.9, §11)."""

from __future__ import annotations

import hearth
from hearth.testing import FakeProvider


def test_fake_provider_gemini_caching() -> None:
    fake = FakeProvider(provider="gemini", model="gemini-2.5-flash")

    long_sys = "Instructions: " + ("You are an AI assistant. " * 450)
    contents1 = [{"role": "user", "content": "Hello turn 1"}]

    # Call 1: cold start write
    resp1 = fake.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents1,
        config={"system_instruction": long_sys},
        ts=100.0,
    )
    assert resp1.usage_metadata.prompt_token_count > 2048
    assert resp1.usage_metadata.cached_content_token_count == 0

    # Call 2: turn 2 with same system prompt (cache hit)
    contents2 = [
        {"role": "user", "content": "Hello turn 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Hello turn 2"},
    ]
    resp2 = fake.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents2,
        config={"system_instruction": long_sys},
        ts=110.0,
    )
    assert resp2.usage_metadata.cached_content_token_count > 2048


def test_fake_provider_openai_caching() -> None:
    fake = FakeProvider(provider="openai", model="gpt-4o")

    long_sys = "Instructions: " + ("You are an AI assistant. " * 200)
    msgs1 = [
        {"role": "system", "content": long_sys},
        {"role": "user", "content": "Question 1"},
    ]

    resp1 = fake.chat.completions.create(
        model="gpt-4o",
        messages=msgs1,
        ts=100.0,
    )
    assert resp1.usage.prompt_tokens > 1024
    assert resp1.usage.prompt_tokens_details["cached_tokens"] == 0

    msgs2 = [
        {"role": "system", "content": long_sys},
        {"role": "user", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "user", "content": "Question 2"},
    ]
    resp2 = fake.chat.completions.create(
        model="gpt-4o",
        messages=msgs2,
        ts=110.0,
    )
    assert resp2.usage.prompt_tokens_details["cached_tokens"] > 1024


def test_fake_provider_anthropic_caching() -> None:
    fake = FakeProvider(provider="anthropic", model="claude-3-5-sonnet")

    long_sys = "Instructions: " + ("You are an AI assistant. " * 200)
    msgs1 = [{"role": "user", "content": "Question 1"}]

    resp1 = fake.messages.create(
        model="claude-3-5-sonnet",
        system=long_sys,
        messages=msgs1,
        ts=100.0,
    )
    assert resp1.usage.input_tokens > 1024
    assert resp1.usage.cache_read_input_tokens == 0
    assert resp1.usage.cache_creation_input_tokens > 1024

    msgs2 = [
        {"role": "user", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "user", "content": "Question 2"},
    ]
    resp2 = fake.messages.create(
        model="claude-3-5-sonnet",
        system=long_sys,
        messages=msgs2,
        ts=110.0,
    )
    assert resp2.usage.cache_read_input_tokens > 1024


def test_wrap_default_mode_is_safe() -> None:
    fake = FakeProvider(provider="gemini", model="gemini-2.5-flash")
    wrapped = hearth.wrap(fake)
    assert wrapped.mode == "safe"


def test_fake_provider_wrapped_by_hearth() -> None:
    fake = FakeProvider(provider="gemini", model="gemini-2.5-flash")
    wrapped = hearth.wrap(fake, mode="safe")

    long_sys = "System instructions: " + ("Guide for operations. " * 250)
    resp = wrapped.models.generate_content(
        model="gemini-2.5-flash",
        contents=[{"role": "user", "content": "Test"}],
        config={"system_instruction": long_sys},
    )
    assert resp is not None
