"""Live provider contract tests (BUILD_HANDBOOK §9 and §10).

Per provider:
1. Two identical calls: reads > 0 on the second call.
2. One deliberate break: the guard names it with the right level.

These tests run nightly against live APIs when API keys are available, costing real money.
Marked with @pytest.mark.contract.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import hearth
from hearth.guard import PrefixGuard
from hearth.trace import TraceRecorder


@pytest.mark.contract
def test_contract_gemini_caching_and_break(tmp_path: Path) -> None:
    """Live contract test for Google Gemini (BUILD_HANDBOOK §9)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not configured for live contract test")

    from google import genai

    client = genai.Client(api_key=api_key)
    recorder = TraceRecorder(trace_dir=tmp_path)
    wrapped = hearth.wrap(client, mode="safe", recorder=recorder)
    session_id = "contract-gemini-live"

    large_context = "This is a contract test knowledge base.\n" * 3000
    contents = [
        {"role": "user", "parts": [{"text": f"Context: {large_context}\nQuestion: What is 2+2?"}]}
    ]

    # Call 1: Baseline cache write/miss
    resp1 = wrapped.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        session_id=session_id,
    )
    assert resp1 is not None

    # Call 2: Identical request (must read from cache: reads > 0)
    resp2 = wrapped.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        session_id=session_id,
    )
    assert resp2 is not None
    cached_tokens = getattr(resp2.usage_metadata, "cached_content_token_count", 0) or 0
    assert cached_tokens > 0, "Second identical call did not read from Gemini prompt cache"

    # Call 3: Deliberate break (mutate prefix)
    broken_contents = [
        {
            "role": "user",
            "parts": [{"text": f"Mutated Context: {large_context}\nQuestion: What is 2+2?"}],
        }
    ]
    resp3 = wrapped.models.generate_content(
        model="gemini-2.5-flash",
        contents=broken_contents,
        session_id=session_id,
    )
    assert resp3 is not None

    # Verify guard named the break
    trace = recorder.read_session(session_id)
    assert len(trace) == 3
    breaks = trace[2].get("breaks", [])
    assert len(breaks) > 0, "Guard did not detect deliberate prefix mutation on call 3"
    assert breaks[0].get("cause") in ("system_changed", "history_rewritten")


@pytest.mark.contract
def test_contract_openai_caching_and_break(tmp_path: Path) -> None:
    """Live contract test for OpenAI (BUILD_HANDBOOK §9)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not configured for live contract test")

    import openai

    client = openai.OpenAI(api_key=api_key)
    recorder = TraceRecorder(trace_dir=tmp_path)
    wrapped = hearth.wrap(client, mode="safe", recorder=recorder)
    session_id = "contract-openai-live"

    large_context = "This is a contract test knowledge base.\n" * 1500
    messages = [
        {"role": "system", "content": f"Context: {large_context}"},
        {"role": "user", "content": "What is 2+2?"},
    ]

    # Call 1: Baseline cache write
    resp1 = wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        session_id=session_id,
    )
    assert resp1 is not None

    # Call 2: Identical request (must read from cache: reads > 0)
    resp2 = wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        session_id=session_id,
    )
    assert resp2 is not None
    details = getattr(resp2.usage, "prompt_tokens_details", None)
    cached_tokens = getattr(details, "cached_tokens", 0) if details else 0
    assert cached_tokens > 0, "Second identical call did not read from OpenAI prompt cache"

    # Call 3: Deliberate break (mutate system prompt)
    broken_messages = [
        {"role": "system", "content": f"Mutated Context: {large_context}"},
        {"role": "user", "content": "What is 2+2?"},
    ]
    resp3 = wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=broken_messages,
        session_id=session_id,
    )
    assert resp3 is not None

    # Verify guard named the break with system level
    trace = recorder.read_session(session_id)
    assert len(trace) == 3
    breaks = trace[2].get("breaks", [])
    assert len(breaks) > 0, "Guard did not detect deliberate prefix break on call 3"
    assert breaks[0].get("cause") in ("system_changed", "history_rewritten")


@pytest.mark.contract
def test_contract_guard_break_verification() -> None:
    """Verifies that PrefixGuard correctly detects deliberate prefix breaks."""
    guard = PrefixGuard(min_prefix_tokens=500)

    # Call 1 baseline
    ev1 = guard.evaluate_call(
        curr_params={"model": "gpt-4o", "temperature": 0.0},
        curr_tools=[],
        curr_system="Baseline system message",
        curr_messages=[{"role": "user", "content": "hello"}],
        total_tokens=1000,
        ts=100.0,
        provider_read_tokens=0,
    )
    assert ev1 is None

    # Call 2: Identical with cache hit
    ev2 = guard.evaluate_call(
        curr_params={"model": "gpt-4o", "temperature": 0.0},
        curr_tools=[],
        curr_system="Baseline system message",
        curr_messages=[{"role": "user", "content": "hello"}],
        total_tokens=1000,
        ts=105.0,
        provider_read_tokens=800,
    )
    assert ev2 is None

    # Call 3: Deliberate break (tool definitions mutated)
    ev3 = guard.evaluate_call(
        curr_params={"model": "gpt-4o", "temperature": 0.0},
        curr_tools=[{"name": "new_tool", "description": "added"}],
        curr_system="Baseline system message",
        curr_messages=[{"role": "user", "content": "hello"}],
        total_tokens=1000,
        ts=110.0,
        provider_read_tokens=0,
    )
    assert ev3 is not None
    assert ev3.cause == "tools_changed"
    assert ev3.level == "tools"
    assert ev3.user_caused is True
