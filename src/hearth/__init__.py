"""Hearth: embeddable context engine that keeps an AI agent's prompt cache warm."""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal, TypeVar

from hearth import tools
from hearth.trace import TraceRecorder, get_trace_recorder

__version__ = "0.1.0a1"
__all__ = [
    "wrap",
    "session",
    "volatile",
    "tools",
    "Mode",
    "SessionContext",
    "HearthPrefixBreak",
    "get_trace_recorder",
    "TraceRecorder",
]

Mode = Literal["observe", "safe", "optimize"]


class HearthPrefixBreak(Exception):
    """Raised before sending when strict=True and a user-caused prefix break is detected."""

    def __init__(self, message: str, cause: str, level: str, message_index: int | None = None):
        super().__init__(message)
        self.cause = cause
        self.level = level
        self.message_index = message_index


class SessionContext:
    """Manages context and hints for a Hearth-tracked agent session."""

    def __init__(self, session_id: str, record: bool = False):
        self.session_id = session_id
        self.record = record
        self._volatile_notes: list[str] = []
        self._expected_pause: bool = False
        self._expected_calls: int | None = None

    def volatile(self, text: str) -> None:
        """Add a volatile piece of text (e.g. timestamp, query snippet) to the tail."""
        self._volatile_notes.append(text)

    def pop_volatile(self) -> list[str]:
        """Pop all pending volatile notes for inclusion in the upcoming turn."""
        notes = list(self._volatile_notes)
        self._volatile_notes.clear()
        return notes

    def expect_pause(self) -> None:
        """Hint to planner that an upcoming human interaction or long tool pause is expected."""
        self._expected_pause = True

    def expect_calls(self, n: int) -> None:
        """Hint to the planner the expected number of remaining calls."""
        self._expected_calls = n


_current_session: contextvars.ContextVar[SessionContext | None] = contextvars.ContextVar(
    "_current_session", default=None
)


@contextmanager
def session(name: str | None = None, record: bool = False) -> Iterator[SessionContext]:
    """Context manager for an explicit Hearth session."""
    session_id = name or f"session-{id(object())}"
    ctx = SessionContext(session_id=session_id, record=record)
    token = _current_session.set(ctx)
    try:
        yield ctx
    finally:
        _current_session.reset(token)


def get_current_session() -> SessionContext | None:
    return _current_session.get()


def volatile(text: str) -> None:
    """Convenience helper to attach a volatile note to the active session."""
    ctx = get_current_session()
    if ctx is not None:
        ctx.volatile(text)


T = TypeVar("T")


def wrap(
    client: T,
    mode: Mode = "observe",
    record: bool = False,
    strict: bool = False,
    recorder: TraceRecorder | None = None,
) -> T:
    """Wrap a provider client with Hearth context management.

    In 'observe' mode (default for M0), the client makes byte-identical requests
    and records traces and metrics with zero behaviour change.
    """
    from hearth.wrapper import WrappedClientProxy

    proxy = WrappedClientProxy(client, mode=mode, record=record, strict=strict, recorder=recorder)
    return proxy  # type: ignore[return-value]
