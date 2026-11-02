"""Prompt layout optimization and volatile relocation (BUILD_HANDBOOK §5.1, INV-05)."""

from __future__ import annotations

from typing import Any

from hearth.guard import VOLATILE_PATTERN
from hearth.offload import offload_large_tool_outputs


def relocate_volatile_in_system(
    system: str, messages: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Relocate volatile elements from static system prompt to the user turn tail (INV-05).

    Returns (optimized_system, optimized_messages, changes).
    """
    if not system:
        return system, messages, []

    lines = system.splitlines()
    static_lines: list[str] = []
    relocated_snippets: list[str] = []

    for line in lines:
        if VOLATILE_PATTERN.search(line):
            relocated_snippets.append(line.strip())
        else:
            static_lines.append(line)

    if not relocated_snippets:
        return system, messages, []

    optimized_system = "\n".join(static_lines).strip()
    optimized_messages = [dict(m) for m in messages]
    changes: list[dict[str, Any]] = []

    # Format relocated context block
    relocated_block = "\n".join(relocated_snippets)

    # Attach to the latest user message or add as a user message
    target_idx = None
    for idx in range(len(optimized_messages) - 1, -1, -1):
        if optimized_messages[idx].get("role") == "user":
            target_idx = idx
            break

    if target_idx is not None:
        curr_content = optimized_messages[target_idx].get("content", "")
        if isinstance(curr_content, str):
            optimized_messages[target_idx]["content"] = (
                f"{curr_content}\n\n[Runtime Context:\n{relocated_block}]"
            )
        changes.append(
            {
                "kind": "volatile_relocated",
                "source": "system",
                "target_message_index": target_idx,
                "snippets": relocated_snippets,
            }
        )
    else:
        # No user message yet: append as initial turn
        optimized_messages.append(
            {"role": "user", "content": f"[Runtime Context:\n{relocated_block}]"}
        )
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
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply all optimize-mode layout transformations and record all changes (INV-05)."""
    all_changes: list[dict[str, Any]] = []

    # 1. Relocate volatile elements from system prefix to tail
    new_system, new_messages, reloc_changes = relocate_volatile_in_system(system, messages)
    all_changes.extend(reloc_changes)

    # 2. Offload large tool outputs if read tool is registered
    new_messages, offload_changes = offload_large_tool_outputs(new_messages, tools)
    all_changes.extend(offload_changes)

    return new_system, new_messages, all_changes


def optimize_chat_messages(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
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
    new_system, new_rest, changes = optimize_layout(system, rest, tools)
    system_message = dict(messages[system_idx])
    system_message["content"] = new_system
    head = [dict(message) for message in messages[:system_idx]]
    return head + [system_message] + new_rest, changes
