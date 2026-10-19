"""Prompt cache planner: breakpoints, TTL, and cache key planning (BUILD_HANDBOOK §5.3, §5.4, INV-11)."""

from __future__ import annotations

from dataclasses import dataclass, field

from hearth.segments import Segment, StabilityClass


@dataclass(frozen=True)
class Breakpoint:
    segment_kind: str
    segment_index: int
    ttl_seconds: int = 300


@dataclass
class CachePlan:
    should_cache: bool
    breakpoints: list[Breakpoint] = field(default_factory=list)
    prompt_cache_key: str | None = None


def plan_breakpoints(
    provider: str,
    segments: list[Segment],
    expected_calls: int = 2,
    use_long_ttl_on_stable: bool = False,
    session_id: str | None = None,
) -> CachePlan:
    """Decide whether and where to place cache breakpoints and metadata (INV-11).

    Rules:
    1. If expected_calls <= 1, do not add cache metadata (skips write premium on one-shots).
    2. Respect provider limits: max 4 breakpoints for Anthropic and OpenAI.
    3. Place 1-hour TTL on stable prefix only, before 5-minute entries (INV-11).
    """
    if expected_calls <= 1:
        return CachePlan(should_cache=False, breakpoints=[])

    breakpoints: list[Breakpoint] = []
    stable_segments = [
        s for s in segments if s.stability in (StabilityClass.STATIC, StabilityClass.SESSION)
    ]
    append_segments = [s for s in segments if s.stability == StabilityClass.APPEND]

    # Breakpoint 1: Stable boundary (STATIC / SESSION)
    if stable_segments:
        last_stable = stable_segments[-1]
        ttl = 3600 if use_long_ttl_on_stable else 300
        breakpoints.append(
            Breakpoint(
                segment_kind=last_stable.kind,
                segment_index=last_stable.index,
                ttl_seconds=ttl,
            )
        )

    # Breakpoints on rolling conversation tail
    # Provider limit is max 4 breakpoints (Anthropic, OpenAI)
    remaining_slots = 4 - len(breakpoints)
    if append_segments and remaining_slots > 0:
        # Choose most recent append messages (closer to turn tail)
        selected_appends = append_segments[-remaining_slots:]
        for seg in selected_appends:
            breakpoints.append(
                Breakpoint(
                    segment_kind=seg.kind,
                    segment_index=seg.index,
                    ttl_seconds=300,  # Conversation tail always gets 5-minute TTL
                )
            )

    # Enforce INV-11: 1-hour TTL entries must precede 5-minute entries
    breakpoints.sort(key=lambda b: 0 if b.ttl_seconds == 3600 else 1)

    # Ensure hard limit of 4 breakpoints
    final_breakpoints = breakpoints[:4]

    cache_key = f"hearth:{session_id}" if session_id else None

    return CachePlan(
        should_cache=True,
        breakpoints=final_breakpoints,
        prompt_cache_key=cache_key,
    )
