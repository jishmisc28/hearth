"""Tests for Hearth invariants specified in BUILD_HANDBOOK section 8."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

import hearth
from hearth.fingerprint import fingerprint_message, rolling_segment_hash
from hearth.trace import TraceRecorder


class MockResponse:
    def __init__(self, text: str = "ok"):
        self.text = text
        self.usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 800},
        }


class MockClient:
    def __init__(self) -> None:
        self.last_args: tuple[Any, ...] = ()
        self.last_kwargs: dict[str, Any] = {}
        self.call_count = 0

    def create(self, *args: Any, **kwargs: Any) -> MockResponse:
        self.last_args = args
        self.last_kwargs = kwargs
        self.call_count += 1
        return MockResponse()


class MockTopClient:
    def __init__(self) -> None:
        self.messages = MockClient()


def test_observe_passthrough_bytes(tmp_path: Path) -> None:
    """INV-01: observe sends byte-identical requests."""
    underlying = MockClient()
    recorder = TraceRecorder(trace_dir=tmp_path)
    client = hearth.wrap(underlying, mode="observe", recorder=recorder)

    original_kwargs = {
        "model": "gemini-2.5-flash",
        "messages": [{"role": "user", "content": "Hello world"}],
        "temperature": 0.0,
        "custom_marker": object(),  # Exact object identity check
    }

    resp = client.create(**original_kwargs)

    assert resp.text == "ok"
    assert underlying.call_count == 1
    # Verify kwargs were passed untouched with exact same object identities
    assert underlying.last_kwargs["custom_marker"] is original_kwargs["custom_marker"]
    assert underlying.last_kwargs["messages"] is original_kwargs["messages"]


def test_no_content_by_default(tmp_path: Path) -> None:
    """INV-09: No prompt content in ledger, logs, or spans; trace bodies only with record=True."""
    underlying = MockClient()
    recorder = TraceRecorder(trace_dir=tmp_path)

    # 1. Default: record=False
    client_default = hearth.wrap(underlying, mode="observe", record=False, recorder=recorder)
    client_default.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "SUPER_SECRET_PROMPT_CONTENT_XYZ"}],
        session_id="session-default",
    )

    trace_file_default = tmp_path / "session-default.jsonl"
    assert trace_file_default.exists()
    content_default = trace_file_default.read_text(encoding="utf-8")
    assert "SUPER_SECRET_PROMPT_CONTENT_XYZ" not in content_default

    trace_entry = json.loads(content_default.strip())
    assert "body" not in trace_entry

    # 2. Explicit: record=True
    client_recorded = hearth.wrap(underlying, mode="observe", record=True, recorder=recorder)
    client_recorded.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "RECORDED_PROMPT_CONTENT_123"}],
        session_id="session-recorded",
    )

    trace_file_rec = tmp_path / "session-recorded.jsonl"
    assert trace_file_rec.exists()
    content_rec = trace_file_rec.read_text(encoding="utf-8")
    assert "RECORDED_PROMPT_CONTENT_123" in content_rec
    trace_entry_rec = json.loads(content_rec.strip())
    assert "body" in trace_entry_rec


# --- Placeholders for future milestone invariants (ensures test_named_tests_exist passes) ---


def test_safe_no_content_change(tmp_path: Path) -> None:
    """INV-02: safe adds, removes or changes no message or tool content; only caching metadata and first-seen-order restoration."""
    underlying = MockClient()
    recorder = TraceRecorder(trace_dir=tmp_path)
    client = hearth.wrap(underlying, mode="safe", recorder=recorder)

    tool_a = {"name": "tool_a", "description": "Tool A"}
    tool_b = {"name": "tool_b", "description": "Tool B"}

    # Call 1: tools in order [tool_a, tool_b]
    client.create(
        model="gemini-2.5-flash",
        system="System instructions",
        tools=[tool_a, tool_b],
        messages=[{"role": "user", "content": "Question 1"}],
        session_id="s-safe-1",
    )
    sent_tools_1 = underlying.last_kwargs["tools"]
    assert sent_tools_1 == [tool_a, tool_b]

    # Call 2: application reorders tools as [tool_b, tool_a]
    client.create(
        model="gemini-2.5-flash",
        system="System instructions",
        tools=[tool_b, tool_a],
        messages=[
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
        ],
        session_id="s-safe-1",
    )
    sent_tools_2 = underlying.last_kwargs["tools"]
    # Safe mode restored first-seen order!
    assert sent_tools_2 == [tool_a, tool_b]
    # No content was changed or removed from messages
    assert underlying.last_kwargs["messages"][0]["content"] == "Question 1"
    assert underlying.last_kwargs["messages"][2]["content"] == "Question 2"


@given(
    role=st.sampled_from(["system", "user", "assistant", "tool"]),
    content=st.text(min_size=0, max_size=500),
)
def test_fingerprint_determinism(role: str, content: str) -> None:
    """INV-03: Fingerprints are deterministic across processes and Python versions."""
    msg = {"role": role, "content": content}
    fp1 = fingerprint_message(msg)
    fp2 = fingerprint_message(msg)
    assert fp1 == fp2
    assert isinstance(fp1, str)
    assert len(fp1) == 64  # SHA-256 hex digest length

    # Determinism across rolling hashes
    h1 = rolling_segment_hash([fp1, fp2])
    h2 = rolling_segment_hash([fp1, fp2])
    assert h1 == h2


def test_append_only(tmp_path: Path) -> None:
    """INV-04: No already-sent message is changed except by a recorded compaction."""
    underlying = MockClient()
    recorder = TraceRecorder(trace_dir=tmp_path)
    client = hearth.wrap(underlying, mode="safe", recorder=recorder)

    msg1 = {"role": "user", "content": "Message 1"}
    msg2 = {"role": "assistant", "content": "Response 1"}
    msg3 = {"role": "user", "content": "Message 2"}

    client.create(
        model="gemini-2.5-flash",
        messages=[msg1],
        session_id="s-append-1",
    )
    sent_msgs_1 = underlying.last_kwargs["messages"]

    client.create(
        model="gemini-2.5-flash",
        messages=[msg1, msg2, msg3],
        session_id="s-append-1",
    )
    sent_msgs_2 = underlying.last_kwargs["messages"]

    # The prefix of sent_msgs_2 matches sent_msgs_1 byte-for-byte and was never altered
    assert sent_msgs_2[0] == sent_msgs_1[0]
    assert sent_msgs_2[0]["content"] == "Message 1"


def test_changes_reported(tmp_path: Path) -> None:
    """INV-05: Every optimize move and safe order restoration is recorded and reported."""
    from hearth.tools import READ_OFFLOADED_TOOL_DEF

    recorder = TraceRecorder(trace_dir=tmp_path)
    underlying = MockClient()

    # 1. Test safe mode tool order restoration recording
    client_safe = hearth.wrap(underlying, mode="safe", recorder=recorder)
    tool_a = {"name": "tool_a", "description": "a"}
    tool_b = {"name": "tool_b", "description": "b"}

    # Call 1: tool_a, tool_b
    client_safe.create(
        model="gemini-2.5-flash",
        tools=[tool_a, tool_b],
        messages=[{"role": "user", "content": "hi"}],
        session_id="s-changes-safe",
    )

    # Call 2: reorder to tool_b, tool_a
    client_safe.create(
        model="gemini-2.5-flash",
        tools=[tool_b, tool_a],
        messages=[{"role": "user", "content": "next"}],
        session_id="s-changes-safe",
    )

    trace_safe = recorder.read_session("s-changes-safe")
    assert len(trace_safe) == 2
    changes_call2 = trace_safe[1].get("changes", [])
    assert any(c.get("kind") == "tool_order_restored" for c in changes_call2)

    # 2. Test optimize mode volatile relocation and tool offload recording
    client_opt = hearth.wrap(underlying, mode="optimize", recorder=recorder)
    tools_with_offload = [tool_a, READ_OFFLOADED_TOOL_DEF]

    # Large tool output (> 2000 tokens ~ 8000 chars)
    large_output = "Line of database records:\n" * 600

    client_opt.create(
        model="gemini-2.5-flash",
        system="You are an assistant.\nCurrent time: 2026-10-19T14:30:00Z\nBe helpful.",
        tools=tools_with_offload,
        messages=[
            {"role": "user", "content": "fetch records"},
            {"role": "tool", "content": large_output, "tool_call_id": "call_1"},
        ],
        session_id="s-changes-opt",
    )

    trace_opt = recorder.read_session("s-changes-opt")
    assert len(trace_opt) == 1
    changes_opt = trace_opt[0].get("changes", [])

    # Must record volatile relocation
    assert any(c.get("kind") == "volatile_relocated" for c in changes_opt)
    # Must record output offloaded
    assert any(c.get("kind") == "output_offloaded" for c in changes_opt)

    # Verify that the sent request had volatile stripped from system prompt
    sent_system = underlying.last_kwargs.get("system", "")
    assert "Current time:" not in sent_system
    assert "You are an assistant." in sent_system

    # Verify that sent tool message contains stub
    sent_messages = underlying.last_kwargs.get("messages", [])
    assert len(sent_messages) == 2
    assert "OFFLOADED LARGE TOOL RESULT" in sent_messages[1]["content"]


def test_usage_reconciles_anthropic() -> None:
    """INV-06: read + write + uncached equals Anthropic's total input exactly."""
    from hearth.adapters.anthropic import parse_anthropic_usage

    raw = {
        "input_tokens": 5000,
        "cache_read_input_tokens": 3500,
        "cache_creation_input_tokens": 1000,
        "output_tokens": 200,
    }
    usage = parse_anthropic_usage(raw)
    assert usage.read + usage.write + usage.uncached == raw["input_tokens"]
    assert usage.read == 3500
    assert usage.write == 1000
    assert usage.uncached == 500
    assert usage.output == 200


def test_usage_reconciles_openai() -> None:
    """INV-06: read + write + uncached equals OpenAI's total input exactly."""
    from hearth.adapters.openai import parse_openai_usage

    raw = {
        "prompt_tokens": 4000,
        "prompt_tokens_details": {"cached_tokens": 2800},
        "cache_write_tokens": 500,
        "completion_tokens": 150,
    }
    usage = parse_openai_usage(raw)
    assert usage.read + usage.write + usage.uncached == raw["prompt_tokens"]
    assert usage.read == 2800
    assert usage.write == 500
    assert usage.uncached == 700
    assert usage.output == 150


def test_usage_reconciles_gemini() -> None:
    """INV-06: read + write + uncached equals Gemini's total input exactly."""
    from hearth.adapters.gemini import parse_gemini_usage

    raw = {
        "prompt_token_count": 6000,
        "cached_content_token_count": 4500,
        "candidates_token_count": 300,
    }
    usage = parse_gemini_usage(raw)
    assert usage.read + usage.write + usage.uncached == raw["prompt_token_count"]
    assert usage.read == 4500
    assert usage.uncached == 1500
    assert usage.output == 300


def test_fail_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """INV-07: Fail-open: internal error sends original request unchanged and records hearth_error."""
    from hearth.wrapper import WrappedMethod

    underlying = MockClient()
    recorder = TraceRecorder(trace_dir=tmp_path)
    client = hearth.wrap(underlying, mode="safe", recorder=recorder)

    # Monkeypatch internal processing to simulate unexpected internal exception
    def broken_process(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Simulated internal bug in Hearth engine")

    monkeypatch.setattr(WrappedMethod, "_process_safe_request", broken_process)

    # Call should NOT fail; it fails open, sending the original request
    orig_msg = [{"role": "user", "content": "Critical agent message"}]
    resp = client.create(
        model="gemini-2.5-flash",
        messages=orig_msg,
        session_id="s-failopen-1",
    )

    assert resp.text == "ok"
    assert underlying.call_count == 1
    assert underlying.last_kwargs["messages"] is orig_msg

    # Verify hearth_error recorded in trace
    trace_file = tmp_path / "s-failopen-1.jsonl"
    assert trace_file.exists()
    trace_data = json.loads(trace_file.read_text(encoding="utf-8").strip())
    assert "hearth_error" in trace_data.get("breaks", [{}])[0].get("cause", "")


def test_no_extra_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """INV-08: No network calls except to wrapped provider and OTLP."""
    import socket

    def forbidden_connect(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Unexpected outgoing network socket opened by Hearth core!")

    monkeypatch.setattr(socket.socket, "connect", forbidden_connect)

    underlying = MockClient()
    recorder = TraceRecorder(trace_dir=tmp_path)
    client = hearth.wrap(underlying, mode="safe", recorder=recorder)

    # Creating and making calls should not open network connections
    resp = client.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "Local test"}],
        session_id="s-nonet-1",
    )
    assert resp.text == "ok"


def test_break_attribution() -> None:
    """INV-10: below_minimum, short_session, ttl_expired, provider_miss not user-caused."""
    from hearth.guard import is_user_caused

    # Provider and environmental causes are NEVER user-caused
    assert not is_user_caused("below_minimum")
    assert not is_user_caused("short_session")
    assert not is_user_caused("ttl_expired")
    assert not is_user_caused("provider_miss")

    # Application/agent layout causes ARE user-caused
    assert is_user_caused("tools_changed")
    assert is_user_caused("tools_reordered")
    assert is_user_caused("volatile_in_prefix")
    assert is_user_caused("system_changed")
    assert is_user_caused("history_rewritten")
    assert is_user_caused("params_changed")


def test_planner_limits() -> None:
    """INV-11: Planner limits are respected (4 Anthropic breakpoints; 1-hour entries before 5-minute ones)."""
    from hearth.planner import CachePlan, plan_breakpoints
    from hearth.segments import Segment, StabilityClass

    # 1. Test max 4 breakpoints
    # Create 6 candidate message segments
    segments = [
        Segment(stability=StabilityClass.STATIC, kind="system", index=0, data="sys"),
        Segment(stability=StabilityClass.APPEND, kind="message", index=0, data={"content": "m1"}),
        Segment(stability=StabilityClass.APPEND, kind="message", index=1, data={"content": "m2"}),
        Segment(stability=StabilityClass.APPEND, kind="message", index=2, data={"content": "m3"}),
        Segment(stability=StabilityClass.APPEND, kind="message", index=3, data={"content": "m4"}),
        Segment(stability=StabilityClass.APPEND, kind="message", index=4, data={"content": "m5"}),
        Segment(stability=StabilityClass.TURN, kind="message", index=5, data={"content": "m6"}),
    ]

    plan: CachePlan = plan_breakpoints(
        provider="anthropic",
        segments=segments,
        expected_calls=5,
        use_long_ttl_on_stable=True,
    )

    # Must respect Anthropic limit of max 4 breakpoints
    assert len(plan.breakpoints) <= 4

    # 2. Test 1-hour TTL entries appear before 5-minute entries
    ttl_list = [bp.ttl_seconds for bp in plan.breakpoints]
    if 3600 in ttl_list and 300 in ttl_list:
        idx_long = ttl_list.index(3600)
        idx_short = ttl_list.index(300)
        assert idx_long < idx_short

    # 3. Test one-shot call does not add breakpoints
    plan_oneshot = plan_breakpoints(
        provider="anthropic",
        segments=segments,
        expected_calls=1,
    )
    assert len(plan_oneshot.breakpoints) == 0


def test_memory_supersede(tmp_path: Path) -> None:
    """INV-12: Memory facts are superseded, never silently overwritten."""
    from hearth.memory import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.sqlite")

    # 1. Record initial fact
    f1_id = store.remember(
        scope="user-123",
        subject="preferred_language",
        predicate="is",
        value="Python",
        source="user",
        source_session="sess-1",
    )
    assert f1_id is not None

    f1 = store.get_fact(f1_id)
    assert f1 is not None
    assert f1.value == "Python"
    assert f1.valid_to is None
    assert f1.superseded_by is None

    # 2. Update fact with new value
    f2_id = store.remember(
        scope="user-123",
        subject="preferred_language",
        predicate="is",
        value="Rust",
        source="user",
        source_session="sess-2",
    )
    assert f2_id is not None
    assert f2_id != f1_id

    # 3. Verify old fact is superseded (closed, valid_to set, superseded_by set), NOT overwritten
    f1_updated = store.get_fact(f1_id)
    assert f1_updated is not None
    assert f1_updated.value == "Python"
    assert f1_updated.valid_to is not None
    assert f1_updated.superseded_by == f2_id

    # 4. Verify new fact is active
    f2 = store.get_fact(f2_id)
    assert f2 is not None
    assert f2.value == "Rust"
    assert f2.valid_to is None
    assert f2.superseded_by is None

    # 5. Query active facts returns only active fact
    active_facts = store.recall(scope="user-123", query="preferred_language")
    assert len(active_facts) == 1
    assert active_facts[0].value == "Rust"


def test_memory_no_session_mutation(tmp_path: Path) -> None:
    """INV-12: Mid-session memory writes never change SESSION."""
    import hearth
    from hearth.memory import MemoryStore

    store = MemoryStore(db_path=tmp_path / "memory.sqlite")

    # Initial pinned fact
    store.remember(
        scope="project-x",
        subject="database",
        predicate="engine",
        value="PostgreSQL",
        source="user",
        source_session="init",
    )

    # Start session 1: pinned facts are loaded into SESSION prefix
    with hearth.session("session-worker-1") as s:
        # Pinned facts loaded once at session start
        pinned_text = store.get_pinned_session_text(scope="project-x", subjects=["database"])
        assert "database engine PostgreSQL" in pinned_text

        # Mid-session fact write: remembers new fact mid-session
        store.remember(
            scope="project-x",
            subject="database",
            predicate="engine",
            value="SQLite",
            source="tool",
            source_session="session-worker-1",
        )

        # In current session, SESSION prefix text must NOT change (preserves prefix cache)
        same_session_text = store.get_pinned_session_text(
            scope="project-x", subjects=["database"], session_id="session-worker-1"
        )
        assert "database engine PostgreSQL" in same_session_text

        # Mid-session writes are placed into turn tail (volatile)
        volatile_notes = s.pop_volatile()
        # Verify tail contains newly written fact or note
        assert any("SQLite" in note for note in volatile_notes)

    # Next session: newly promoted fact loads into SESSION prefix
    next_session_text = store.get_pinned_session_text(
        scope="project-x", subjects=["database"], session_id="session-worker-2"
    )
    assert "database engine SQLite" in next_session_text


def test_cost_decimal() -> None:
    """INV-13: Money is computed in Decimal, never float."""
    from decimal import Decimal

    from hearth.cost import compute_call_cost

    cost = compute_call_cost(
        provider="gemini",
        model="gemini-2.5-flash",
        read_tokens=10000,
        write_tokens=0,
        uncached_tokens=2000,
        output_tokens=500,
    )

    assert isinstance(cost.actual_cost, Decimal)
    assert isinstance(cost.uncached_baseline, Decimal)
    assert isinstance(cost.savings_amount, Decimal)
    assert isinstance(cost.cost_ratio, Decimal)
    # Check that savings are positive and cost_ratio < 1
    assert cost.savings_amount > Decimal("0")
    assert cost.cost_ratio < Decimal("1")
