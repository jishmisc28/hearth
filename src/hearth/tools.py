"""Hearth built-in tools for context offloading (BUILD_HANDBOOK §5.5)."""

from __future__ import annotations

from typing import Any

from hearth.offload import get_blob_store

READ_OFFLOADED_TOOL_DEF: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_offloaded",
        "description": (
            "Read characters from an offloaded large tool result by handle. "
            "Use this when you need detailed sections of a previously offloaded tool output."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "string",
                    "description": "The unique SHA-256 blob handle of the offloaded result.",
                },
                "start": {
                    "type": "integer",
                    "description": "Start character offset (0-indexed, default 0).",
                    "default": 0,
                },
                "end": {
                    "type": "integer",
                    "description": "End character offset (optional; reads to end if omitted).",
                },
            },
            "required": ["handle"],
        },
    },
}


def read_offloaded(handle: str, start: int = 0, end: int | None = None) -> str:
    """Read a slice of offloaded content from the local blob store."""
    store = get_blob_store()
    content = store.get(handle)
    if content is None:
        return f"Error: Offloaded handle '{handle}' not found in local blob store."

    if end is not None:
        return content[start:end]
    return content[start:]
