"""Prompt cache planner: breakpoints, TTL, and cache key planning (BUILD_HANDBOOK §5.3, §5.4, INV-11)."""

from __future__ import annotations

import time
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


class TTLOptimizer:
    """Predicts inter-call gaps and chooses between 5-minute and 1-hour TTL (BUILD_HANDBOOK §5.4).

    Break-even rule (§5.4):
    For a stable prefix of P tokens with k expected gaps longer than 5 minutes before session ends:
    - 5-minute TTL rewrites P at each long gap -> ~1.25 * k * P extra cost.
    - 1-hour TTL writes once at 2.0 * P instead of 1.25 * P -> 0.75 * P extra cost.
    - Use 1 hour if k >= 1 and the session is expected to continue past the gap.
    """

    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self._last_call_time: dict[str, float] = {}
        self._gap_ewma: dict[str, float] = {}
        self._session_decisions: dict[str, bool] = {}

    def record_call(self, session_id: str, timestamp: float | None = None) -> None:
        """Record a call timestamp and update exponential moving average of inter-call gaps."""
        ts = timestamp if timestamp is not None else time.time()
        if session_id in self._last_call_time:
            gap = ts - self._last_call_time[session_id]
            if session_id in self._gap_ewma:
                self._gap_ewma[session_id] = (
                    self.alpha * gap + (1.0 - self.alpha) * self._gap_ewma[session_id]
                )
            else:
                self._gap_ewma[session_id] = gap
        self._last_call_time[session_id] = ts

    def should_use_long_ttl(
        self,
        session_id: str | None = None,
        expected_calls: int = 2,
        expected_pause: bool = False,
    ) -> bool:
        """Evaluate if 1-hour TTL on stable prefix saves money over 5-minute TTL (§5.4)."""
        if expected_calls <= 1:
            return False

        # If decision already established for this session, preserve it (§5.4 once per session rule)
        if session_id and session_id in self._session_decisions:
            return self._session_decisions[session_id]

        decision = False
        if expected_pause:
            decision = True
        elif session_id and session_id in self._gap_ewma:
            # If EWMA inter-call gap exceeds 300 seconds (5 mins), gap k >= 1 is anticipated
            if self._gap_ewma[session_id] > 300.0:
                decision = True

        if session_id:
            self._session_decisions[session_id] = decision
        return decision

    def clear(self) -> None:
        """Clear optimizer state."""
        self._last_call_time.clear()
        self._gap_ewma.clear()
        self._session_decisions.clear()


_global_ttl_optimizer = TTLOptimizer()


def get_ttl_optimizer() -> TTLOptimizer:
    return _global_ttl_optimizer


def plan_breakpoints(
    provider: str,
    segments: list[Segment],
    expected_calls: int = 2,
    use_long_ttl_on_stable: bool | None = None,
    session_id: str | None = None,
    expected_pause: bool = False,
) -> CachePlan:
    """Decide whether and where to place cache breakpoints and metadata (INV-11).

    Rules:
    1. If expected_calls <= 1, do not add cache metadata (skips write premium on one-shots).
    2. Respect provider limits: max 4 breakpoints for Anthropic and OpenAI.
    3. Place 1-hour TTL on stable prefix only, before 5-minute entries (INV-11).
    """
    if expected_calls <= 1:
        return CachePlan(should_cache=False, breakpoints=[])

    # Determine whether 1-hour TTL on stable prefix is economically advantageous (§5.4)
    if use_long_ttl_on_stable is not None:
        long_ttl_active = use_long_ttl_on_stable
    else:
        long_ttl_active = get_ttl_optimizer().should_use_long_ttl(
            session_id=session_id,
            expected_calls=expected_calls,
            expected_pause=expected_pause,
        )

    breakpoints: list[Breakpoint] = []
    stable_segments = [
        s for s in segments if s.stability in (StabilityClass.STATIC, StabilityClass.SESSION)
    ]
    append_segments = [s for s in segments if s.stability == StabilityClass.APPEND]

    # Breakpoint 1: Stable boundary (STATIC / SESSION)
    if stable_segments:
        last_stable = stable_segments[-1]
        ttl = 3600 if long_ttl_active else 300
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
