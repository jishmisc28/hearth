"""Offline token counting and estimation helpers."""

from __future__ import annotations

import importlib
import json
from typing import Any

# Optional tiktoken support
_tiktoken_encoding = None
try:
    _tiktoken_mod = importlib.import_module("tiktoken")
    _tiktoken_encoding = _tiktoken_mod.get_encoding("cl100k_base")
except Exception:
    pass


def count_text_tokens(text: str, model: str = "gemini-2.5-flash") -> int:
    """Offline token estimation for text.

    Uses tiktoken if available for GPT models, or calibrated character-per-token ratio
    (approx 3.85 chars/token for code & technical text) with minimum 1 token for non-empty text.
    """
    if not text:
        return 0

    if _tiktoken_encoding is not None and ("gpt" in model.lower() or "openai" in model.lower()):
        return len(_tiktoken_encoding.encode(text))

    # Calibrated character-per-token estimate across code and prose
    # 3.85 characters/token matches Gemini tokenization benchmarks closely
    char_len = len(text)
    estimated = max(1, int(round(char_len / 3.85)))
    return estimated


def count_message_tokens(message: dict[str, Any], model: str = "gemini-2.5-flash") -> int:
    """Estimate token count for a single message including role metadata framing."""
    tokens = 4  # Per-message overhead (role, formatting tokens)
    content = message.get("content", "")
    if isinstance(content, str):
        tokens += count_text_tokens(content, model=model)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                tokens += count_text_tokens(block, model=model)
            elif isinstance(block, dict):
                text = block.get("text") or json.dumps(block)
                tokens += count_text_tokens(text, model=model)
    return tokens


def count_tool_tokens(tool: dict[str, Any], model: str = "gemini-2.5-flash") -> int:
    """Estimate tokens for a tool schema definition."""
    serialized = json.dumps(tool, sort_keys=True)
    return count_text_tokens(serialized, model=model) + 8  # Schema framing overhead
