"""Planned history compaction economics and scheduling (BUILD_HANDBOOK §5.6)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from hearth.cost import get_model_pricing


@dataclass(frozen=True)
class CompactionPlan:
    """Economic evaluation of compacting H history tokens into S summary tokens."""

    history_tokens: int
    summary_tokens: int
    one_time_cost_usd: Decimal
    saving_per_call_usd: Decimal
    payback_calls_k: int
    should_compact: bool
    reason: str


def compute_compaction_payback(
    *,
    provider: str,
    model: str,
    history_tokens: int,
    summary_tokens: int,
    tail_tokens: int = 0,
    expected_remaining_calls: int = 10,
    context_limit_tokens: int = 128_000,
    current_total_tokens: int = 0,
) -> CompactionPlan:
    """Compute whether compacting H tokens into S tokens pays back before session end (§5.6).

    one-time cost = p_in * (r * H) + p_out * S + p_in * w * (S + tail)
    saving per call = p_in * r * (H - S)
    k* = one-time cost / saving per call
    """
    pricing = get_model_pricing(provider, model)
    h_dec = Decimal(history_tokens)
    s_dec = Decimal(summary_tokens)
    tail_dec = Decimal(tail_tokens)

    # 1. One-time cost
    # Summary call reads H from cache: p_in * r * H
    read_h_cost = pricing.input_price_per_token * (pricing.read_multiplier * h_dec)
    # Summary output cost: p_out * S
    output_s_cost = pricing.output_price_per_token * s_dec
    # Rewrite after the system breakpoint: p_in * w * (S + tail)
    write_rewrite_cost = pricing.input_price_per_token * (
        pricing.write_multiplier * (s_dec + tail_dec)
    )

    one_time_cost = (read_h_cost + output_s_cost + write_rewrite_cost).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )

    # 2. Saving per call
    # H was being read from cache anyway, now only S is read: saving = p_in * r * (H - S)
    token_delta = max(Decimal(0), h_dec - s_dec)
    saving_per_call = (
        pricing.input_price_per_token * pricing.read_multiplier * token_delta
    ).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    # 3. Payback calls k*
    if saving_per_call > Decimal(0):
        k_star = float(one_time_cost / saving_per_call)
        payback_k = max(1, math.ceil(k_star))
    else:
        payback_k = 999_999

    # 4. Compaction decision:
    # A: Context window limit requires it
    must_compact_for_limit = current_total_tokens > 0 and current_total_tokens >= int(
        context_limit_tokens * 0.85
    )

    # B: Economic payback pays back within expected remaining calls
    pays_back_economically = expected_remaining_calls >= payback_k

    should_compact = must_compact_for_limit or pays_back_economically
    if must_compact_for_limit:
        reason = f"Context window limit nearing threshold ({current_total_tokens}/{context_limit_tokens})"
    elif pays_back_economically:
        reason = f"Economically optimal: pays back in {payback_k} calls (<= {expected_remaining_calls} remaining)"
    else:
        reason = (
            f"Does not pay back: needs {payback_k} calls (> {expected_remaining_calls} remaining)"
        )

    return CompactionPlan(
        history_tokens=history_tokens,
        summary_tokens=summary_tokens,
        one_time_cost_usd=one_time_cost,
        saving_per_call_usd=saving_per_call,
        payback_calls_k=payback_k,
        should_compact=should_compact,
        reason=reason,
    )
