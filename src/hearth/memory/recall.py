"""Convenience memory recall and pinning functions (BUILD_HANDBOOK §5.7)."""

from __future__ import annotations

from hearth.memory.store import Fact, MemoryStore

_GLOBAL_STORE: MemoryStore | None = None


def get_default_memory_store() -> MemoryStore:
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = MemoryStore()
    return _GLOBAL_STORE


def set_default_memory_store(store: MemoryStore) -> None:
    global _GLOBAL_STORE
    _GLOBAL_STORE = store


def remember(
    scope: str,
    subject: str,
    predicate: str,
    value: str,
    source: str = "user",
    source_session: str | None = None,
    tainted: bool = False,
) -> int:
    """Store a fact in the default memory store."""
    return get_default_memory_store().remember(
        scope=scope,
        subject=subject,
        predicate=predicate,
        value=value,
        source=source,
        source_session=source_session,
        tainted=tainted,
    )


def recall(scope: str, query: str, k: int = 5) -> list[Fact]:
    """Recall active facts matching query in scope."""
    return get_default_memory_store().recall(scope=scope, query=query, k=k)


def pin(scope: str, subjects: list[str]) -> list[Fact]:
    """Retrieve pinned facts for session start."""
    return get_default_memory_store().pin(scope=scope, subjects=subjects)
