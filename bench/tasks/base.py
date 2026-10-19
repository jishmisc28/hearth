"""Base models and definitions for pre-registered benchmark tasks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchTask:
    """A pre-registered, frozen benchmark task."""

    id: str
    title: str
    instructions: str
    user_query: str
    tools: list[dict[str, Any]]
    tool_handler: Callable[[str, dict[str, Any]], str]
    checker: Callable[[str, list[dict[str, Any]]], bool]
    expected_turns: int = 3
    tags: list[str] = field(default_factory=list)
