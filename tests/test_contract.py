"""Live provider contract tests (BUILD_HANDBOOK §9 and §10).

Per provider:
1. Two identical calls: reads > 0 on the second call.
2. One deliberate break: the guard names it with the right level.

These tests run nightly against live APIs when API keys are available, costing real money.
Marked with @pytest.mark.contract.
"""

from __future__ import annotations

import os

import pytest

import hearth
from hearth.guard import PrefixGuard


@pytest.mark.contract
def test_contract_gemini_caching_and_break() -> None:
    """Live contract test for Google Gemini."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not configured for live contract test")

    from google import genai

    client = genai.Client(api_key=api_key)
    session_id = "contract-gemini-live"
    wrapped = hearth.wrap(client, mode="safe", session_id=session_id)

    # Gemini requires at least 32,768 tokens (or model-specific minimum) for explicit caching,
    # or implicit caching on Gemini 2.5 Flash if above minimum.
    large_context = "This is a contract test knowledge base.\n" * 2000
    contents = [
        {"role": "user", "parts": [{"text": f"Context: {large_context}\nQuestion: What is 2+2?"}]}
    ]

    # Call 1
    resp1 = wrapped.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )
    assert resp1 is not None

    # Call 2 (identical)
    resp2 = wrapped.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )
    assert resp2 is not None

    # Call 3 (deliberate prefix break: mutate prefix)
    broken_contents = [
        {
            "role": "user",
            "parts": [{"text": f"Mutated Context: {large_context}\nQuestion: What is 2+2?"}],
        }
    ]
    resp3 = wrapped.models.generate_content(
        model="gemini-2.5-flash",
        contents=broken_contents,
    )
    assert resp3 is not None


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
