"""Replay CLI and trace evaluation engine (BUILD_HANDBOOK §5.9, §6.2, M4)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from hearth.cost import compute_call_cost
from hearth.guard import PrefixGuard
from hearth.layout import optimize_layout
from hearth.sim.cache_sim import CacheSimulator


@dataclass
class ReplayModeSummary:
    mode: str
    total_input: int
    read_tokens: int
    write_tokens: int
    uncached_tokens: int
    read_pct: float
    written_pct: float
    uncached_pct: float
    cost_usd: Decimal
    no_cache_cost_usd: Decimal
    cost_ratio: Decimal
    user_caused_breaks: int


def replay_trace_events(
    calls: list[dict[str, Any]],
    mode: str = "safe",
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
) -> ReplayModeSummary:
    """Replay a sequence of recorded call events through the simulator under a specific policy mode."""
    sim = CacheSimulator(provider=provider, model=model)
    guard = PrefixGuard(strict=False)

    tot_read = 0
    tot_write = 0
    tot_uncached = 0
    tot_input = 0
    total_cost = Decimal("0")
    total_no_cache_cost = Decimal("0")
    user_caused_breaks = 0

    first_seen_tools: list[str] = []

    for call_idx, call in enumerate(calls, start=1):
        req = call.get("request", {})
        kwargs = req.get("kwargs", {}) if isinstance(req, dict) else {}
        ts = float(call.get("ts", call_idx * 10.0))

        system = str(kwargs.get("system", ""))
        messages = list(kwargs.get("messages", []))
        tools = kwargs.get("tools")
        if isinstance(tools, list):
            tools = list(tools)
        else:
            tools = None

        # Mode transformations
        if mode == "safe":
            # Restore first seen tool ordering
            if tools:
                curr_names = [
                    str(t.get("name")) for t in tools if isinstance(t, dict) and t.get("name")
                ]
                if not first_seen_tools and curr_names:
                    first_seen_tools = list(curr_names)
                elif first_seen_tools and curr_names != first_seen_tools:
                    tool_map = {t.get("name"): t for t in tools if isinstance(t, dict)}
                    reordered = [tool_map[n] for n in first_seen_tools if n in tool_map]
                    for t in tools:
                        if t not in reordered:
                            reordered.append(t)
                    tools = reordered
        elif mode == "optimize":
            # Relocate volatile timestamps and offload large results
            system, messages, _ = optimize_layout(
                system=system,
                messages=messages,
                tools=tools,
            )

        # PrefixGuard evaluation
        ev = guard.evaluate_call(
            curr_params={"model": model},
            curr_tools=tools or [],
            curr_system=system,
            curr_messages=messages,
            total_tokens=sum(len(str(m.get("content", ""))) // 4 for m in messages),
            ts=ts,
        )
        if ev is not None and ev.user_caused:
            user_caused_breaks += 1

        # Simulate cache
        sim_res = sim.simulate_call(
            call_index=call_idx,
            messages=messages,
            tools=tools,
            system=system if system else None,
            ts=ts,
        )

        tot_read += sim_res.predicted_read
        tot_write += sim_res.predicted_write
        tot_uncached += sim_res.predicted_uncached
        tot_input += sim_res.total_input

        # Compute cost
        cost_info = compute_call_cost(
            provider=provider,
            model=model,
            read_tokens=sim_res.predicted_read,
            write_tokens=sim_res.predicted_write,
            uncached_tokens=sim_res.predicted_uncached,
            output_tokens=50,
        )
        total_cost += cost_info.actual_cost
        total_no_cache_cost += cost_info.uncached_baseline

    read_pct = (tot_read / tot_input * 100.0) if tot_input > 0 else 0.0
    written_pct = (tot_write / tot_input * 100.0) if tot_input > 0 else 0.0
    uncached_pct = (tot_uncached / tot_input * 100.0) if tot_input > 0 else 0.0
    cost_ratio = (total_cost / total_no_cache_cost) if total_no_cache_cost > 0 else Decimal("1.0")

    return ReplayModeSummary(
        mode=mode,
        total_input=tot_input,
        read_tokens=tot_read,
        write_tokens=tot_write,
        uncached_tokens=tot_uncached,
        read_pct=read_pct,
        written_pct=written_pct,
        uncached_pct=uncached_pct,
        cost_usd=total_cost,
        no_cache_cost_usd=total_no_cache_cost,
        cost_ratio=cost_ratio,
        user_caused_breaks=user_caused_breaks,
    )


def replay_trace_file(
    trace_path: str | Path,
    modes: list[str] | None = None,
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
) -> list[ReplayModeSummary]:
    """Load trace file and replay across specified modes."""
    path = Path(trace_path)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_path}")

    calls: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                calls.append(json.loads(line))

    if modes is None:
        modes = ["observe", "safe", "optimize"]

    return [replay_trace_events(calls=calls, mode=m, provider=provider, model=model) for m in modes]


def format_replay_table(summaries: list[ReplayModeSummary]) -> str:
    """Format replay summaries into canonical CLI table output."""
    header = f"{'mode':<10}{'read':<9}{'written':<11}{'uncached':<11}{'input cost':<13}{'user-caused breaks'}"
    lines = [header]
    for s in summaries:
        read_s = f"{s.read_pct:.0f}%"
        writ_s = f"{s.written_pct:.0f}%"
        unc_s = f"{s.uncached_pct:.0f}%"
        cost_s = f"{float(s.cost_ratio):.2f}\u00d7"
        lines.append(
            f"{s.mode:<10}{read_s:<9}{writ_s:<11}{unc_s:<11}{cost_s:<13}{s.user_caused_breaks}"
        )
    return "\n".join(lines)
