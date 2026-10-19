"""Unit tests for cache planner and TTL optimizer (BUILD_HANDBOOK §5.3, §5.4, INV-11)."""

from hearth.planner import CachePlan, TTLOptimizer, plan_breakpoints
from hearth.segments import Segment, StabilityClass


def test_ttl_optimizer_oneshot() -> None:
    """TTLOptimizer rejects long TTL when expected_calls <= 1 to avoid write premium."""
    opt = TTLOptimizer()
    assert not opt.should_use_long_ttl(session_id="sess-1", expected_calls=1, expected_pause=True)


def test_ttl_optimizer_expected_pause() -> None:
    """Application pause hint s.expect_pause() triggers 1-hour TTL on stable prefix."""
    opt = TTLOptimizer()
    assert opt.should_use_long_ttl(session_id="sess-2", expected_calls=3, expected_pause=True)


def test_ttl_optimizer_gap_ewma() -> None:
    """When observed inter-call gap EWMA exceeds 300s (5m), 1-hour TTL is selected."""
    opt = TTLOptimizer(alpha=0.5)
    session_id = "sess-long-gaps"

    opt.record_call(session_id, timestamp=1000.0)
    opt.record_call(session_id, timestamp=1400.0)  # gap 400s > 300s
    opt.record_call(session_id, timestamp=1800.0)  # gap 400s > 300s

    assert opt.should_use_long_ttl(session_id=session_id, expected_calls=2)


def test_ttl_optimizer_sticky_decision_per_session() -> None:
    """Once decided for a session, decision is preserved (§5.4 once-per-session rule)."""
    opt = TTLOptimizer()
    session_id = "sess-sticky"

    decision1 = opt.should_use_long_ttl(
        session_id=session_id, expected_calls=3, expected_pause=True
    )
    assert decision1 is True

    # Subsequent check without expected_pause still preserves True for the session
    decision2 = opt.should_use_long_ttl(
        session_id=session_id, expected_calls=3, expected_pause=False
    )
    assert decision2 is True


def test_plan_breakpoints_ttl_placement_inv_11() -> None:
    """INV-11: 1-hour TTL placed on stable prefix only; conversation tail always gets 300s."""
    segments = [
        Segment(kind="system", index=0, stability=StabilityClass.STATIC, data="System prompt"),
        Segment(kind="session", index=1, stability=StabilityClass.SESSION, data="Session context"),
        Segment(kind="message", index=2, stability=StabilityClass.APPEND, data="User turn 1"),
        Segment(kind="message", index=3, stability=StabilityClass.APPEND, data="Model reply 1"),
    ]

    plan: CachePlan = plan_breakpoints(
        provider="anthropic",
        segments=segments,
        expected_calls=3,
        use_long_ttl_on_stable=True,
    )

    assert plan.should_cache is True
    assert len(plan.breakpoints) <= 4

    # First breakpoint is stable boundary with 3600s TTL
    assert plan.breakpoints[0].ttl_seconds == 3600
    assert plan.breakpoints[0].segment_kind == "session"

    # Rolling append breakpoints must always have 300s TTL (never written at 2x price)
    tail_breakpoints = [b for b in plan.breakpoints if b.segment_kind == "message"]
    for b in tail_breakpoints:
        assert b.ttl_seconds == 300

    # INV-11: 1-hour entries must precede 5-minute entries
    ttls = [b.ttl_seconds for b in plan.breakpoints]
    assert ttls == sorted(ttls, reverse=True)  # 3600 before 300
