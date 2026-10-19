"""Switch-or-stay model router evaluating cost and context retention (BUILD_HANDBOOK §5.8).

Evaluates whether to stay on current model, switch models, or delegate sub-tasks
using closed-form break-even economics and exact Decimal arithmetic (INV-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from hearth.cost import get_model_pricing

RouteVerdict = Literal["stay", "switch", "delegate"]


@dataclass(frozen=True)
class RouteDecision:
    """Outcome of switch-or-stay evaluation."""

    verdict: RouteVerdict
    current_model: str
    target_model: str
    expected_calls: int
    stay_cost: Decimal
    switch_cost: Decimal
    delegate_cost: Decimal | None
    break_even_n: Decimal | None
    price_ratio_q: Decimal
    reason: str


def calculate_break_even_n(
    price_a: Decimal,
    price_b: Decimal,
    read_multiplier: Decimal,
    write_multiplier: Decimal,
) -> Decimal | None:
    """Calculate the closed-form threshold calls n* where switching to B pays back.

    Formula (BUILD_HANDBOOK §5.8):
        q = p_B / p_A
        If q >= 1: switching never saves money (returns None).
        If q < 1: n* = (q * w) / (r * (1 - q))
    """
    if price_a <= Decimal("0"):
        return None

    q = price_b / price_a
    if q >= Decimal("1"):
        return None

    denominator = read_multiplier * (Decimal("1") - q)
    if denominator <= Decimal("0"):
        return None

    numerator = q * write_multiplier
    return numerator / denominator


def evaluate_route(
    current_provider: str,
    current_model: str,
    target_provider: str,
    target_model: str,
    prefix_tokens: int,
    expected_calls: int,
    expected_new_input_tokens: int = 100,
    expected_output_tokens: int = 500,
    subtask_prefix_tokens: int | None = None,
    subtask_expected_calls: int = 1,
) -> RouteDecision:
    """Evaluate whether to stay, switch, or delegate using exact Decimal pricing (INV-13).

    Rules (BUILD_HANDBOOK §5.8):
    1. Switching to model B writes cold prefix at B's write price on call 1.
    2. Later calls on B read from cache at B's read price.
    3. If target is more expensive (q >= 1), switching never saves money -> verdict is 'stay'.
    4. If subtask_prefix_tokens is provided and delegate cost < min(stay, switch),
       verdict is 'delegate'.
    5. If switch_cost < stay_cost, verdict is 'switch'.
    6. Otherwise, verdict is 'stay'.
    """
    p_curr = get_model_pricing(current_provider, current_model)
    p_targ = get_model_pricing(target_provider, target_model)

    p_in_a = p_curr.input_price_per_token
    p_out_a = p_curr.output_price_per_token
    r_a = p_curr.read_multiplier

    p_in_b = p_targ.input_price_per_token
    p_out_b = p_targ.output_price_per_token
    r_b = p_targ.read_multiplier
    w_b = p_targ.write_multiplier

    p_tokens = Decimal(str(prefix_tokens))
    n_calls = Decimal(str(expected_calls))
    t_new = Decimal(str(expected_new_input_tokens))
    out_tokens = Decimal(str(expected_output_tokens))

    # Closed-form price ratio q
    q = (p_in_b / p_in_a) if p_in_a > Decimal("0") else Decimal("1")
    break_even_n = calculate_break_even_n(p_in_a, p_in_b, r_b, w_b)

    # 1. Stay cost: reads warm prefix on current model for all n calls
    cost_per_call_stay = p_in_a * (r_a * p_tokens + t_new) + p_out_a * out_tokens
    stay_cost = n_calls * cost_per_call_stay

    # 2. Switch cost:
    # Call 1 on B: cold write of prefix at write multiplier w_b
    call_1_switch = p_in_b * (w_b * p_tokens + t_new) + p_out_b * out_tokens
    # Remaining n - 1 calls on B: read from B's warm cache
    if expected_calls > 1:
        calls_rest_switch = (n_calls - Decimal("1")) * (
            p_in_b * (r_b * p_tokens + t_new) + p_out_b * out_tokens
        )
    else:
        calls_rest_switch = Decimal("0")
    switch_cost = call_1_switch + calls_rest_switch

    # 3. Delegate cost (if subtask context is specified)
    delegate_cost: Decimal | None = None
    if subtask_prefix_tokens is not None and subtask_expected_calls > 0:
        p_sub = Decimal(str(subtask_prefix_tokens))
        m_calls = Decimal(str(subtask_expected_calls))
        # Subtask runs as a fresh session on B with only p_sub tokens:
        # First call writes p_sub on B, remaining m - 1 read on B
        sub_call_1 = p_in_b * (w_b * p_sub + t_new) + p_out_b * out_tokens
        sub_calls_rest = (
            (m_calls - Decimal("1")) * (p_in_b * (r_b * p_sub + t_new) + p_out_b * out_tokens)
            if subtask_expected_calls > 1
            else Decimal("0")
        )
        total_subtask_cost = sub_call_1 + sub_calls_rest
        # Main session stays on A for remaining calls
        remaining_main_calls = max(Decimal("1"), n_calls - m_calls)
        main_stay_cost = remaining_main_calls * cost_per_call_stay
        delegate_cost = total_subtask_cost + main_stay_cost

    # Decision logic
    if q >= Decimal("1"):
        verdict: RouteVerdict = "stay"
        reason = f"Target model {target_model} is not cheaper (price ratio q={q:.2f} >= 1.0); stay on {current_model}."
    elif delegate_cost is not None and delegate_cost < stay_cost and delegate_cost < switch_cost:
        verdict = "delegate"
        savings = min(stay_cost, switch_cost) - delegate_cost
        reason = (
            f"Delegate subtask to {target_model} with smaller context ({subtask_prefix_tokens} tokens): "
            f"saves ${savings:.6f} vs full prefix cold rewrite."
        )
    elif switch_cost < stay_cost:
        verdict = "switch"
        savings = stay_cost - switch_cost
        b_even_str = f"{break_even_n:.1f}" if break_even_n is not None else "N/A"
        reason = (
            f"Switch to {target_model}: n={expected_calls} exceeds break-even n*={b_even_str}; "
            f"saves ${savings:.6f} over {expected_calls} calls."
        )
    else:
        verdict = "stay"
        b_even_str = f"{break_even_n:.1f}" if break_even_n is not None else "N/A"
        reason = (
            f"Stay on {current_model}: n={expected_calls} below break-even n*={b_even_str}; "
            f"cold write penalty on {target_model} would cost more than cache reads on {current_model}."
        )

    return RouteDecision(
        verdict=verdict,
        current_model=current_model,
        target_model=target_model,
        expected_calls=expected_calls,
        stay_cost=stay_cost,
        switch_cost=switch_cost,
        delegate_cost=delegate_cost,
        break_even_n=break_even_n,
        price_ratio_q=q,
        reason=reason,
    )
