"""Pre-registered 5 mixed-difficulty benchmark tasks for M6 (BUILD_HANDBOOK §10.2, §5.8)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class MixedBenchTask:
    id: str
    title: str
    primary_model: str
    secondary_model: str
    prefix_tokens: int
    expected_calls: int
    subtask_tokens: int | None
    has_pause: bool
    checker: Callable[[dict[str, Any]], bool]


MIXED_TASKS: list[MixedBenchTask] = [
    MixedBenchTask(
        id="mixed_heavy_reasoning",
        title="Complex analysis with straightforward validation sub-calls",
        primary_model="gemini-2.5-flash",
        secondary_model="gemini-1.5-flash",
        prefix_tokens=8000,
        expected_calls=6,  # n=6 > n* (~2.2) -> switches validation calls to secondary
        subtask_tokens=None,
        has_pause=False,
        checker=lambda res: (
            res.get("verdict") == "switch"
            and res.get("savings_pct", 0.0) > 10.0
            and res.get("passed", False)
        ),
    ),
    MixedBenchTask(
        id="mixed_delegate_subtask",
        title="Codebase analysis with small-scope extraction delegation",
        primary_model="gemini-2.5-flash",
        secondary_model="gemini-1.5-flash",
        prefix_tokens=15000,
        expected_calls=4,
        subtask_tokens=600,  # Small subtask context << 15000
        has_pause=False,
        checker=lambda res: (
            res.get("verdict") == "delegate"
            and res.get("savings_pct", 0.0) > 20.0
            and res.get("passed", False)
        ),
    ),
    MixedBenchTask(
        id="mixed_ttl_pause",
        title="Multi-turn human-in-the-loop task with 10-minute pause",
        primary_model="claude-3-5-sonnet-20241022",
        secondary_model="claude-3-5-haiku-20241022",
        prefix_tokens=10000,
        expected_calls=3,
        subtask_tokens=None,
        has_pause=True,  # 1-hour TTL avoids 5-minute TTL cache expiration rewrite
        checker=lambda res: (
            res.get("long_ttl_used", False)
            and res.get("savings_pct", 0.0) > 10.0
            and res.get("passed", False)
        ),
    ),
    MixedBenchTask(
        id="mixed_short_stay",
        title="Short task below break-even threshold avoiding cold write penalty",
        primary_model="gemini-2.5-flash",
        secondary_model="gemini-1.5-flash",
        prefix_tokens=20000,
        expected_calls=1,  # Short run: below break-even -> stays
        subtask_tokens=None,
        has_pause=False,
        checker=lambda res: (
            res.get("verdict") == "stay"
            and res.get("passed", False)
            and res.get("savings_pct", 0.0) >= 0.0
        ),
    ),
    MixedBenchTask(
        id="mixed_escalation",
        title="Distilled context escalation to primary model on failure",
        primary_model="gemini-2.5-flash",
        secondary_model="gemini-1.5-flash",
        prefix_tokens=10000,
        expected_calls=3,
        subtask_tokens=1200,
        has_pause=False,
        checker=lambda res: (
            res.get("passed", False)
            and res.get("escalated", False)
            and res.get("savings_pct", 0.0) > 5.0
        ),
    ),
]


def get_all_mixed_tasks() -> list[MixedBenchTask]:
    return list(MIXED_TASKS)
