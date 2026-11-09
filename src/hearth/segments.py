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


def _part_text(part: Any) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        if "text" in part:
            return str(part.get("text") or "")
        return str(part)
    text = getattr(part, "text", None)
    if isinstance(text, str):
        return text
    return str(part)


def contents_as_messages(contents: Any) -> list[dict[str, Any]]:
    """Turn Gemini ``contents`` into messages for the guard.

    The provider still receives the original ``contents``. This view is only
    used to count tokens and detect a changed prompt.
    """
    if contents is None:
        return []
    if isinstance(contents, str):
        return [{"role": "user", "content": contents}]
    if not isinstance(contents, list):
        return [{"role": "user", "content": _part_text(contents)}]

    messages: list[dict[str, Any]] = []
    for item in contents:
        if isinstance(item, str):
            messages.append({"role": "user", "content": item})
            continue
        if isinstance(item, dict):
            role = str(item.get("role", "user"))
            if "parts" in item:
                parts = item.get("parts")
                text = (
                    "\n".join(_part_text(part) for part in parts) if isinstance(parts, list) else ""
                )
                messages.append({"role": role, "content": text})
            elif "content" in item:
                messages.append({"role": role, "content": item.get("content")})
            else:
                messages.append({"role": role, "content": str(item)})
            continue
        role = str(getattr(item, "role", "user"))
        parts = getattr(item, "parts", None)
        if isinstance(parts, list):
            messages.append(
                {"role": role, "content": "\n".join(_part_text(part) for part in parts)}
            )
        else:
            messages.append({"role": role, "content": _part_text(item)})
    return messages


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
