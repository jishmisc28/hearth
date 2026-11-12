"""Session dollars are the sum of priced turns, and a projection is labeled."""

from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path


def _summary():
    path = Path(__file__).resolve().parents[1] / "bench" / "live_summary.py"
    spec = importlib.util.spec_from_file_location("live_summary", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nova_session_savings_match_the_price_list() -> None:
    summary = _summary()
    turns = [
        {"turn": 1, "kind": "stable", "read": 0, "write": 8000, "uncached": 6, "output": 2},
        {"turn": 2, "kind": "stable", "read": 8000, "write": 0, "uncached": 6, "output": 2},
    ]
    result = summary.summarize_turns("bedrock", "amazon.nova-micro-v1:0", turns)
    assert Decimal(result["saved_usd"]) > 0
    assert Decimal(result["session_ratio"]) < Decimal("1")
    assert Decimal(result["actual_usd"]) + Decimal(result["saved_usd"]) == Decimal(
        result["baseline_usd"]
    )


def test_a_tool_use_is_followed_by_a_tool_result() -> None:
    path = Path(__file__).resolve().parents[1] / "bench" / "live_session.py"
    spec = importlib.util.spec_from_file_location("live_session", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    content = [{"toolUse": {"toolUseId": "abc", "name": "search_repo", "input": {}}}]
    message = module._tool_result_message(content)
    assert message is not None
    assert message["content"][0]["toolResult"]["toolUseId"] == "abc"
    assert module._tool_result_message([{"text": "ok"}]) is None


def test_projection_is_the_measured_session_times_n() -> None:
    summary = _summary()
    measured = {
        "actual_usd": "0.10",
        "baseline_usd": "0.40",
        "saved_usd": "0.30",
    }
    scaled = summary.project_sessions(measured, 1000)
    assert scaled["saved_usd"] == "300.00"
    assert scaled["label"].startswith("projection")
