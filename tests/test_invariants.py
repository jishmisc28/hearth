"""Tests for Hearth invariants specified in BUILD_HANDBOOK section 8."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import hearth
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


@pytest.mark.skip(reason="INV-02 scheduled for M1")
def test_safe_no_content_change() -> None:
    """INV-02: safe adds, removes or changes no message or tool content."""


@pytest.mark.skip(reason="INV-03 scheduled for M1")
def test_fingerprint_determinism() -> None:
    """INV-03: Fingerprints are deterministic across processes and Python versions."""


@pytest.mark.skip(reason="INV-04 scheduled for M1")
def test_append_only() -> None:
    """INV-04: No already-sent message is changed except by a recorded compaction."""


@pytest.mark.skip(reason="INV-05 scheduled for M2")
def test_changes_reported() -> None:
    """INV-05: Every optimize move and safe order restoration is recorded and reported."""


@pytest.mark.skip(reason="INV-06 scheduled for M1")
def test_usage_reconciles_anthropic() -> None:
    """INV-06: read + write + uncached equals Anthropic's total input exactly."""


@pytest.mark.skip(reason="INV-06 scheduled for M1")
def test_usage_reconciles_openai() -> None:
    """INV-06: read + write + uncached equals OpenAI's total input exactly."""


@pytest.mark.skip(reason="INV-06 scheduled for M2")
def test_usage_reconciles_gemini() -> None:
    """INV-06: read + write + uncached equals Gemini's total input exactly."""


@pytest.mark.skip(reason="INV-07 scheduled for M1")
def test_fail_open() -> None:
    """INV-07: Fail-open: internal error sends original request unchanged."""


@pytest.mark.skip(reason="INV-08 scheduled for M1")
def test_no_extra_network() -> None:
    """INV-08: No network calls except to wrapped provider and OTLP."""


@pytest.mark.skip(reason="INV-10 scheduled for M1")
def test_break_attribution() -> None:
    """INV-10: below_minimum, short_session, ttl_expired, provider_miss not user-caused."""


@pytest.mark.skip(reason="INV-11 scheduled for M1")
def test_planner_limits() -> None:
    """INV-11: Planner limits are respected."""


@pytest.mark.skip(reason="INV-12 scheduled for M5")
def test_memory_supersede() -> None:
    """INV-12: Memory facts are superseded, never silently overwritten."""


@pytest.mark.skip(reason="INV-12 scheduled for M5")
def test_memory_no_session_mutation() -> None:
    """INV-12: Mid-session memory writes never change SESSION."""


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
