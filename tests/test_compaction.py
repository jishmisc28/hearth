"""Tests for planned compaction payback economics (BUILD_HANDBOOK §5.6)."""

from __future__ import annotations

from hearth.compaction import compute_compaction_payback


def test_compaction_payback_formula_gemini() -> None:
    """Verifies that compaction payback calculation matches §5.6 closed form."""
    # Under Gemini 2.5 Flash:
    # 50k history tokens compacted to 5k summary tokens
    plan = compute_compaction_payback(
        provider="gemini",
        model="gemini-2.5-flash",
        history_tokens=50_000,
        summary_tokens=5_000,
        tail_tokens=0,
        expected_remaining_calls=12,
    )

    # Saving per call: p_in * r * (H - S) = p_in * 0.1 * 45,000 = 4,500 * p_in
    assert plan.saving_per_call_usd > 0
    # Payback should be reasonable (~8 to 15 calls depending on write/output multipliers)
    assert 5 <= plan.payback_calls_k <= 20
    assert plan.should_compact is True


def test_compaction_does_not_pay_back_on_short_session() -> None:
    """Compaction should not trigger if expected remaining calls < payback k."""
    plan = compute_compaction_payback(
        provider="gemini",
        model="gemini-2.5-flash",
        history_tokens=50_000,
        summary_tokens=5_000,
        tail_tokens=0,
        expected_remaining_calls=2,  # Only 2 calls remaining
    )

    assert plan.should_compact is False
    assert "Does not pay back" in plan.reason
