"""Five stability classes and request segmentation (BUILD_HANDBOOK §2.4)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class StabilityClass(str, Enum):
    STATIC = "STATIC"
    SESSION = "SESSION"
    APPEND = "APPEND"
    VOLATILE = "VOLATILE"
    TURN = "TURN"


@dataclass(frozen=True)
class Segment:
    """A classified section of the prompt context."""

    stability: StabilityClass
    kind: str  # "tools", "system", "message", "volatile"
    index: int
    data: Any
    fingerprint: str = ""


def classify_message(
    msg_index: int,
    total_messages: int,
    role: str,
    content: Any,
) -> StabilityClass:
    """Classify a message into its stability class.

    The last user or tool message is TURN. Prior messages are APPEND.
    """
    if msg_index == total_messages - 1:
        return StabilityClass.TURN
    return StabilityClass.APPEND


def segment_request(
    system: Any = None,
    tools: list[dict[str, Any]] | None = None,
    messages: list[dict[str, Any]] | None = None,
    volatile_notes: list[str] | None = None,
) -> list[Segment]:
    """Segment a model request into stability classes in canonical provider order:

    tools (STATIC) -> system (STATIC/SESSION) -> messages (APPEND -> TURN) -> volatile tail.
    """
    segments: list[Segment] = []

    # 1. Tools are STATIC
    if tools:
        for idx, tool in enumerate(tools):
            segments.append(
                Segment(
                    stability=StabilityClass.STATIC,
                    kind="tools",
                    index=idx,
                    data=tool,
                )
            )

    # 2. Top-level system prompt is STATIC
    if system is not None:
        segments.append(
            Segment(
                stability=StabilityClass.STATIC,
                kind="system",
                index=0,
                data=system,
            )
        )

    # 3. Conversation messages (APPEND and final TURN)
    if messages:
        n_msgs = len(messages)
        for idx, msg in enumerate(messages):
            role = str(msg.get("role", "user"))
            content = msg.get("content", "")
            stability = classify_message(idx, n_msgs, role, content)
            segments.append(
                Segment(
                    stability=stability,
                    kind="message",
                    index=idx,
                    data=msg,
                )
            )

    # 4. Volatile tail notes
    if volatile_notes:
        for idx, note in enumerate(volatile_notes):
            segments.append(
                Segment(
                    stability=StabilityClass.VOLATILE,
                    kind="volatile",
                    index=idx,
                    data=note,
                )
            )

    return segments
