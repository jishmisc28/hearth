"""Pre-registered 5 multi-session memory benchmark tasks (BUILD_HANDBOOK §9, §10.2, M5)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class MemoryBenchTask:
    id: str
    title: str
    sessions_count: int
    session_queries: list[str]
    checker: Callable[[list[str], Any], bool]


MEMORY_TASKS: list[MemoryBenchTask] = [
    MemoryBenchTask(
        id="mem_config_override",
        title="Configuration override superseding without contradiction",
        sessions_count=3,
        session_queries=[
            "Set system log_level to debug",
            "Update system log_level to info",
            "What is the current system log_level?",
        ],
        checker=lambda answers, store: (
            "info" in answers[-1].lower() and "debug" not in answers[-1].lower()
        ),
    ),
    MemoryBenchTask(
        id="mem_temporal_relocation",
        title="Temporal relocation of user timezone",
        sessions_count=3,
        session_queries=[
            "I am currently based in Tokyo (JST).",
            "I have relocated to London (GMT).",
            "What is my current timezone?",
        ],
        checker=lambda answers, store: (
            "london" in answers[-1].lower() or "gmt" in answers[-1].lower()
        ),
    ),
    MemoryBenchTask(
        id="mem_schema_migration",
        title="Database primary key migration fact",
        sessions_count=3,
        session_queries=[
            "Our user table primary key is integer user_id.",
            "We migrated the user table primary key to uuid.",
            "Which column should be used as the foreign key referencing users?",
        ],
        checker=lambda answers, store: "uuid" in answers[-1].lower(),
    ),
    MemoryBenchTask(
        id="mem_pinned_prefix_stability",
        title="Multi-session pinned facts prefix stability",
        sessions_count=2,
        session_queries=[
            "Pin project core stack: Python, SQLite, Gemini.",
            "Confirm current architecture components and add a runtime note.",
        ],
        checker=lambda answers, store: (
            "sqlite" in answers[-1].lower() and "python" in answers[-1].lower()
        ),
    ),
    MemoryBenchTask(
        id="mem_taint_quarantine",
        title="Untrusted tool output fact held in quarantine",
        sessions_count=2,
        session_queries=[
            "Web scraper extracted company address: 123 Insecure St (unverified).",
            "List all verified company facts.",
        ],
        checker=lambda answers, store: "123 insecure" not in answers[-1].lower(),
    ),
]


def get_all_memory_tasks() -> list[MemoryBenchTask]:
    return list(MEMORY_TASKS)
