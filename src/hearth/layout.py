"""Prompt layout optimization and volatile relocation (BUILD_HANDBOOK §5.1, INV-05)."""

from __future__ import annotations

from typing import Any

from hearth.fingerprint import fingerprint_message
from hearth.guard import VOLATILE_PATTERN
from hearth.offload import offload_large_tool_outputs


class LayoutMemory:
    """Exact suffixes already sent, so a later turn can repeat those bytes.

    Keyed by the index and fingerprint of the application's original message.
    A rewritten message does not match, and the old suffix is not applied to it.
    """

    def __init__(self) -> None:
        self._by_index: dict[int, tuple[str, str]] = {}

    def suffix_for(self, index: int, message: dict[str, Any]) -> str | None:
        found = self._by_index.get(index)
        if found is None:
            return None
        digest, suffix = found
        if digest != fingerprint_message(message):
            return None
        return suffix

    def remember(self, index: int, message: dict[str, Any], suffix: str) -> None:
        self._by_index[index] = (fingerprint_message(message), suffix)

    def __bool__(self) -> bool:
        return bool(self._by_index)


def _with_suffix(message: dict[str, Any], suffix: str) -> dict[str, Any]:
    updated = dict(message)
    content = updated.get("content", "")
    if isinstance(content, str):
        updated["content"] = f"{content}{suffix}"
    return updated


def _runtime_suffix(snippets: list[str]) -> str:
    block = "\n".join(snippets)
    return f"\n\n[Runtime Context:\n{block}]"


def relocate_volatile_in_system(
    system: str,
    messages: list[dict[str, Any]],
    memory: LayoutMemory | None = None,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Relocate volatile elements from static system prompt to the user turn tail (INV-05).

    Returns (optimized_system, optimized_messages, changes).

    When ``memory`` is set, a suffix already sent on a message is written again
    unchanged. A new clock is attached only to a user message that has not been
    sent yet. Writing the new clock onto an earlier message would change bytes
    the provider already saw.
    """
    if not system and not memory:
        return system, messages, []

    lines = system.splitlines() if system else []
    static_lines: list[str] = []
    relocated_snippets: list[str] = []

    for line in lines:
        if VOLATILE_PATTERN.search(line):
            relocated_snippets.append(line.strip())
        else:
            static_lines.append(line)

    if not relocated_snippets and not memory:
        return system, messages, []

    optimized_system = "\n".join(static_lines).strip()
    optimized_messages = [dict(m) for m in messages]
    changes: list[dict[str, Any]] = []

    target_idx = None
    for idx in range(len(optimized_messages) - 1, -1, -1):
        if optimized_messages[idx].get("role") == "user":
            target_idx = idx
            break

    if memory is not None:
        for idx, message in enumerate(optimized_messages):
            if idx == target_idx:
                continue
            stored = memory.suffix_for(idx, message)
            if stored:
                optimized_messages[idx] = _with_suffix(message, stored)
                changes.append(
                    {
                        "kind": "volatile_retained",
                        "source": "system",
                        "target_message_index": idx,
                    }
                )

    if not relocated_snippets:
        return optimized_system, optimized_messages, changes

    suffix = _runtime_suffix(relocated_snippets)
    if target_idx is not None:
        original = optimized_messages[target_idx]
        stored = memory.suffix_for(target_idx, original) if memory is not None else None
        if stored is not None:
            optimized_messages[target_idx] = _with_suffix(original, stored)
            changes.append(
                {
                    "kind": "volatile_retained",
                    "source": "system",
                    "target_message_index": target_idx,
                    "snippets_not_written": relocated_snippets,
                }
            )
        else:
            content = original.get("content", "")
            if isinstance(content, str):
                optimized_messages[target_idx] = _with_suffix(original, suffix)
                if memory is not None:
                    memory.remember(target_idx, original, suffix)
            changes.append(
                {
                    "kind": "volatile_relocated",
                    "source": "system",
                    "target_message_index": target_idx,
                    "snippets": relocated_snippets,
                }
            )
    else:
        block = "\n".join(relocated_snippets)
        optimized_messages.append({"role": "user", "content": f"[Runtime Context:\n{block}]"})
        changes.append(
            {
                "kind": "volatile_relocated",
                "source": "system",
                "target_message_index": len(optimized_messages) - 1,
                "snippets": relocated_snippets,
            }
        )

    return optimized_system, optimized_messages, changes


def optimize_layout(
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    memory: LayoutMemory | None = None,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply all optimize-mode layout transformations and record all changes (INV-05)."""
    all_changes: list[dict[str, Any]] = []

    # 1. Relocate volatile elements from system prefix to tail
    new_system, new_messages, reloc_changes = relocate_volatile_in_system(
        system, messages, memory=memory
    )
    all_changes.extend(reloc_changes)

    # 2. Offload large tool outputs if read tool is registered
    new_messages, offload_changes = offload_large_tool_outputs(new_messages, tools)
    all_changes.extend(offload_changes)

    return new_system, new_messages, all_changes


def optimize_chat_messages(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    memory: LayoutMemory | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Relocate volatile lines inside an OpenAI-style system message.

    Chat Completions keeps the system text in ``messages``, not a top-level
    ``system`` field. The non-volatile lines stay in that message. The clock
    moves onto the latest user message.
    """
    system_idx = None
    for idx, message in enumerate(messages):
        if (
            isinstance(message, dict)
            and message.get("role") == "system"
            and isinstance(message.get("content"), str)
        ):
            system_idx = idx
            break
    if system_idx is None:
        new_messages, changes = offload_large_tool_outputs(list(messages), tools)
        return new_messages, changes

    system = str(messages[system_idx]["content"])
    rest = [dict(message) for i, message in enumerate(messages) if i != system_idx]
    new_system, new_rest, changes = optimize_layout(system, rest, tools, memory=memory)
    system_message = dict(messages[system_idx])
    system_message["content"] = new_system
    head = [dict(message) for message in messages[:system_idx]]
    return head + [system_message] + new_rest, changes
