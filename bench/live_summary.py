"""Turn provider usage into a session summary. Dollars come from providers.toml."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from hearth.cost import compute_call_cost


def summarize_turns(provider: str, model: str, turns: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum a measured session. A turn with an error is omitted from the dollars."""
    actual = Decimal("0")
    baseline = Decimal("0")
    priced_turns: list[dict[str, Any]] = []
    for turn in turns:
        if turn.get("error"):
            priced_turns.append({**turn, "cost_usd": None, "baseline_usd": None})
            continue
        cost = compute_call_cost(
            provider=provider,
            model=model,
            read_tokens=int(turn.get("read") or 0),
            write_tokens=int(turn.get("write") or 0),
            uncached_tokens=int(turn.get("uncached") or 0),
            output_tokens=int(turn.get("output") or 0),
        )
        actual += cost.actual_cost
        baseline += cost.uncached_baseline
        priced_turns.append(
            {
                **turn,
                "cost_usd": str(cost.actual_cost),
                "baseline_usd": str(cost.uncached_baseline),
                "cost_ratio": str(cost.cost_ratio),
            }
        )
    saved = baseline - actual
    ratio = (actual / baseline) if baseline > 0 else Decimal("1")
    return {
        "provider": provider,
        "model": model,
        "turns": priced_turns,
        "actual_usd": str(actual),
        "baseline_usd": str(baseline),
        "saved_usd": str(saved),
        "session_ratio": str(ratio.quantize(Decimal("0.0001"))),
    }


def project_sessions(summary: dict[str, Any], sessions: int) -> dict[str, str]:
    """Scale one measured session. This is arithmetic, not another live run."""
    count = Decimal(sessions)
    return {
        "sessions": str(sessions),
        "actual_usd": str(Decimal(summary["actual_usd"]) * count),
        "baseline_usd": str(Decimal(summary["baseline_usd"]) * count),
        "saved_usd": str(Decimal(summary["saved_usd"]) * count),
        "label": "projection from the measured session, not a separate run",
    }
