"""Tests for prefix guard divergence detection and strict flag."""

import pytest

from hearth import HearthPrefixBreak
from hearth.guard import PrefixGuard


def test_guard_strict_raises_on_user_break() -> None:
    guard = PrefixGuard(strict=True, min_prefix_tokens=100)

    # First call sets state
    guard.evaluate_call(
        curr_params={"model": "gemini-2.5-flash"},
        curr_tools=[{"name": "tool_a"}],
        curr_system="Static system prompt",
        curr_messages=[{"role": "user", "content": "Hello"}],
        total_tokens=500,
        ts=100.0,
    )

    # Second call changes model (params_changed: user-caused)
    with pytest.raises(HearthPrefixBreak) as exc_info:
        guard.evaluate_call(
            curr_params={"model": "gemini-2.0-flash"},  # changed!
            curr_tools=[{"name": "tool_a"}],
            curr_system="Static system prompt",
            curr_messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
                {"role": "user", "content": "Next"},
            ],
            total_tokens=600,
            ts=110.0,
        )

    assert exc_info.value.cause == "params_changed"


def test_guard_strict_does_not_raise_on_non_user_break() -> None:
    guard = PrefixGuard(strict=True, min_prefix_tokens=2048)

    # First call: total tokens below minimum (below_minimum: NOT user-caused)
    event = guard.evaluate_call(
        curr_params={"model": "gemini-2.5-flash"},
        curr_tools=[],
        curr_system="Short",
        curr_messages=[{"role": "user", "content": "Hi"}],
        total_tokens=50,  # below minimum
        ts=100.0,
    )
    # Does not raise!
    assert event is not None
    assert event.cause == "below_minimum"
    assert not event.user_caused
