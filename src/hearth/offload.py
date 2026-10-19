"""Context offloading for large tool results in optimize mode (BUILD_HANDBOOK §5.5)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from hearth.sim.tokens import count_text_tokens

DEFAULT_OFFLOAD_THRESHOLD_TOKENS = 2000
DEFAULT_PREVIEW_CHARS = 250


class BlobStore:
    """Key-value storage for offloaded tool outputs keyed by SHA-256."""

    def __init__(self, storage_dir: Path | None = None):
        self._memory: dict[str, str] = {}
        self.storage_dir = storage_dir
        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)

    def put(self, content: str) -> str:
        """Store content and return its SHA-256 hex digest handle."""
        handle = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self._memory[handle] = content
        if self.storage_dir:
            blob_path = self.storage_dir / f"{handle}.txt"
            if not blob_path.exists():
                blob_path.write_text(content, encoding="utf-8")
        return handle

    def get(self, handle: str) -> str | None:
        """Retrieve stored content by handle."""
        if handle in self._memory:
            return self._memory[handle]
        if self.storage_dir:
            blob_path = self.storage_dir / f"{handle}.txt"
            if blob_path.exists():
                content = blob_path.read_text(encoding="utf-8")
                self._memory[handle] = content
                return content
        return None


_GLOBAL_BLOB_STORE: BlobStore | None = None


def get_blob_store() -> BlobStore:
    """Get the active global BlobStore instance."""
    global _GLOBAL_BLOB_STORE
    if _GLOBAL_BLOB_STORE is None:
        home_blobs = Path.home() / ".hearth" / "blobs"
        try:
            _GLOBAL_BLOB_STORE = BlobStore(storage_dir=home_blobs)
        except Exception:
            _GLOBAL_BLOB_STORE = BlobStore(storage_dir=None)
    return _GLOBAL_BLOB_STORE


def is_read_tool_registered(tools: list[dict[str, Any]] | None) -> bool:
    """Check if hearth.tools.read_offloaded is registered in the client's tools."""
    if not tools:
        return False

    for t in tools:
        name = ""
        if isinstance(t, dict):
            name = t.get("name") or t.get("function", {}).get("name", "")
        elif hasattr(t, "name"):
            name = t.name
        if name in ("read_offloaded", "hearth_read_offloaded"):
            return True
    return False


def offload_large_tool_outputs(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    threshold_tokens: int = DEFAULT_OFFLOAD_THRESHOLD_TOKENS,
    store: BlobStore | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Substitute tool results exceeding threshold with deterministic stubs (INV-05).

    Returns (transformed_messages, changes_recorded).
    If read tool is not registered, offloading is strictly disabled per §5.5.
    """
    if not is_read_tool_registered(tools):
        return messages, []

    if store is None:
        store = get_blob_store()

    new_messages: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []

    for idx, msg in enumerate(messages):
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Check for tool results (either role == 'tool' or tool_result block)
        is_tool_result = role in ("tool", "tool_result") or "tool_call_id" in msg
        if is_tool_result and isinstance(content, str):
            token_count = count_text_tokens(content)
            if token_count >= threshold_tokens:
                handle = store.put(content)
                size_chars = len(content)
                preview = content[:DEFAULT_PREVIEW_CHARS].replace("\n", " ").strip()

                stub = (
                    f"[OFFLOADED LARGE TOOL RESULT: handle={handle}, {size_chars} chars, ~{token_count} tokens. "
                    f"To inspect sections, call read_offloaded(handle='{handle}', start=..., end=...). "
                    f"Preview: {preview}...]"
                )

                new_msg = dict(msg)
                new_msg["content"] = stub
                new_messages.append(new_msg)

                changes.append(
                    {
                        "kind": "output_offloaded",
                        "message_index": idx,
                        "handle": handle,
                        "tokens_saved": token_count,
                        "chars_saved": size_chars,
                    }
                )
                continue

        new_messages.append(msg)

    return new_messages, changes
