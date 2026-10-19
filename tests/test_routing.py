"""Unit and property tests for switch-or-stay routing policy (BUILD_HANDBOOK §5.8, INV-13)."""

from decimal import Decimal

from hearth.policies.route import (
    calculate_break_even_n,
    evaluate_route,
)


def test_calculate_break_even_n_formula() -> None:
    """Validate closed form formula n* = (q * w) / (r * (1 - q)) from BUILD_HANDBOOK §5.8."""
    # Example from §5.8: q = 0.2, r = 0.1, w = 1.25 -> n* = 3.125 (> 3.1)
    p_a = Decimal("10.00")
    p_b = Decimal("2.00")  # q = 0.2
    r = Decimal("0.10")
    w = Decimal("1.25")

    n_star = calculate_break_even_n(p_a, p_b, r, w)
    assert n_star is not None
    assert isinstance(n_star, Decimal)
    assert round(n_star, 3) == Decimal("3.125")


def test_calculate_break_even_more_expensive_target() -> None:
    """If target model is more expensive (q >= 1), switching never saves money."""
    p_a = Decimal("2.00")
    p_b = Decimal("10.00")  # q = 5.0 >= 1
    r = Decimal("0.10")
    w = Decimal("1.25")

    n_star = calculate_break_even_n(p_a, p_b, r, w)
    assert n_star is None


def test_evaluate_route_stay_on_short_run() -> None:
    """When expected calls n < n*, staying on warm cache is cheaper than cold write on target."""
    # Current: Claude 3.5 Sonnet ($3.00/M), Target: Claude 3.5 Haiku ($0.80/M)
    # With 50k prefix, Haiku cold write is $0.050, whereas 2 Sonnet warm reads are only $0.030
    decision = evaluate_route(
        current_provider="anthropic",
        current_model="claude-3-5-sonnet-20241022",
        target_provider="anthropic",
        target_model="claude-3-5-haiku-20241022",
        prefix_tokens=50000,
        expected_calls=2,  # Short run: below break-even
        expected_output_tokens=50,
    )

    assert decision.verdict == "stay"
    assert decision.stay_cost < decision.switch_cost
    assert isinstance(decision.stay_cost, Decimal)
    assert isinstance(decision.switch_cost, Decimal)
    assert "Stay on" in decision.reason


def test_evaluate_route_switch_on_long_run() -> None:
    """When expected calls n > n*, switching to cheaper model amortizes cold write and saves money."""
    # Current: Claude 3.5 Sonnet ($3.00/M), Target: Claude 3.5 Haiku ($0.80/M)
    decision = evaluate_route(
        current_provider="anthropic",
        current_model="claude-3-5-sonnet-20241022",
        target_provider="anthropic",
        target_model="claude-3-5-haiku-20241022",
        prefix_tokens=10000,
        expected_calls=10,  # Long run: well above break-even
    )

    assert decision.verdict == "switch"
    assert decision.switch_cost < decision.stay_cost
    assert "Switch to" in decision.reason


def test_evaluate_route_delegate_subtask() -> None:
    """When a subtask needs only a small context subset, delegate is cheaper than full switch or stay."""
    # Main session has 20,000 token prefix on Sonnet.
    # Subtask needs only 800 tokens on Haiku for 2 calls.
    decision = evaluate_route(
        current_provider="anthropic",
        current_model="claude-3-5-sonnet-20241022",
        target_provider="anthropic",
        target_model="claude-3-5-haiku-20241022",
        prefix_tokens=20000,
        expected_calls=4,
        subtask_prefix_tokens=800,
        subtask_expected_calls=2,
    )

    assert decision.verdict == "delegate"
    assert decision.delegate_cost is not None
    assert decision.delegate_cost < decision.stay_cost
    assert decision.delegate_cost < decision.switch_cost
    assert "Delegate subtask" in decision.reason


def test_evaluate_route_more_expensive_target_stays() -> None:
    """If target is more expensive, router always stays."""
    decision = evaluate_route(
        current_provider="anthropic",
        current_model="claude-3-5-haiku-20241022",
        target_provider="anthropic",
        target_model="claude-3-5-sonnet-20241022",
        prefix_tokens=5000,
        expected_calls=5,
    )

    assert decision.verdict == "stay"
    assert decision.price_ratio_q >= Decimal("1")
    assert "not cheaper" in decision.reason


def test_evaluate_route_decimal_types_inv_13() -> None:
    """INV-13: All monetary calculations in evaluate_route return Decimal."""
    decision = evaluate_route(
        current_provider="gemini",
        current_model="gemini-2.5-flash",
        target_provider="gemini",
        target_model="gemini-1.5-flash",
        prefix_tokens=8000,
        expected_calls=6,
    )

    assert isinstance(decision.stay_cost, Decimal)
    assert isinstance(decision.switch_cost, Decimal)
    assert isinstance(decision.price_ratio_q, Decimal)
    if decision.break_even_n is not None:
        assert isinstance(decision.break_even_n, Decimal)
