"""Cache simulator modeling provider prompt caching rules and calibration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from hearth.cost import load_providers_toml
from hearth.sim.tokens import count_message_tokens, count_text_tokens, count_tool_tokens


@dataclass
class SimulatedCallResult:
    call_index: int
    predicted_read: int
    predicted_write: int
    predicted_uncached: int
    predicted_read_share: float
    total_input: int
    cause: str | None = None


class CacheSimulator:
    """Simulates provider prompt cache behavior from recorded traces."""

    def __init__(self, provider: str = "gemini", model: str = "gemini-2.5-flash"):
        self.provider = provider
        self.model = model
        providers_data = load_providers_toml()
        p_info = providers_data.get("providers", {}).get(provider, {})
        m_info = p_info.get("models", {}).get(model, {})

        self.min_prefix = int(
            m_info.get("min_prefix_tokens", p_info.get("min_prefix_tokens", 2048))
        )
        self.ttl_seconds = float(p_info.get("default_ttl_seconds", 3600.0))

        # Session cache state
        self.cached_prefix_tokens: list[int] = []
        self.cached_prefix_hashes: list[str] = []
        self.last_call_ts: float | None = None

    def reset(self) -> None:
        self.cached_prefix_tokens.clear()
        self.cached_prefix_hashes.clear()
        self.last_call_ts = None

    def simulate_call(
        self,
        call_index: int,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        ts: float = 0.0,
    ) -> SimulatedCallResult:
        """Simulate a single call against provider caching rules."""
        # Check TTL
        ttl_expired = False
        if self.last_call_ts is not None and (ts - self.last_call_ts) > self.ttl_seconds:
            ttl_expired = True
            self.cached_prefix_tokens.clear()
            self.cached_prefix_hashes.clear()

        # Build token blocks and hashes in provider prefix order: tools -> system -> messages
        token_blocks: list[int] = []
        hash_blocks: list[str] = []

        if tools:
            for t in tools:
                tok = count_tool_tokens(t, self.model)
                token_blocks.append(tok)
                hash_blocks.append(f"tool:{t.get('name', '')}:{json.dumps(t, sort_keys=True)}")

        if system:
            tok = count_text_tokens(system, self.model)
            token_blocks.append(tok)
            hash_blocks.append(f"system:{system}")

        for m in messages:
            tok = count_message_tokens(m, self.model)
            token_blocks.append(tok)
            content_str = str(m.get("content", ""))
            hash_blocks.append(f"msg:{m.get('role', '')}:{content_str}")

        total_input = sum(token_blocks)

        # Match prefix against previous cached prefix
        matching_tokens = 0
        matching_blocks = 0
        for i in range(min(len(hash_blocks), len(self.cached_prefix_hashes))):
            if hash_blocks[i] == self.cached_prefix_hashes[i]:
                matching_tokens += token_blocks[i]
                matching_blocks += 1
            else:
                break

        cause = None
        predicted_read = 0
        predicted_write = 0
        predicted_uncached = total_input

        # Cache reading logic
        if matching_tokens >= self.min_prefix and not ttl_expired:
            predicted_read = matching_tokens
            predicted_uncached = total_input - predicted_read
        else:
            if total_input < self.min_prefix:
                cause = "below_minimum"
            elif ttl_expired:
                cause = "ttl_expired"
            elif matching_tokens < self.min_prefix and self.cached_prefix_hashes:
                cause = "volatile_in_prefix"

        # Update cached prefix state
        # In Gemini implicit mode, the entire input becomes cached if >= min_prefix
        if total_input >= self.min_prefix:
            predicted_write = total_input - predicted_read
            self.cached_prefix_tokens = list(token_blocks)
            self.cached_prefix_hashes = list(hash_blocks)
        else:
            self.cached_prefix_tokens = []
            self.cached_prefix_hashes = []

        self.last_call_ts = ts
        read_share = float(predicted_read) / total_input if total_input > 0 else 0.0

        return SimulatedCallResult(
            call_index=call_index,
            predicted_read=predicted_read,
            predicted_write=predicted_write,
            predicted_uncached=predicted_uncached,
            predicted_read_share=read_share,
            total_input=total_input,
            cause=cause,
        )


def compute_calibration_mae(
    actual_read_shares: list[float],
    predicted_read_shares: list[float],
) -> float:
    """Compute Mean Absolute Error (MAE) in read share percentage points.

    Returns value in points (0 to 100).
    """
    if not actual_read_shares or not predicted_read_shares:
        return 0.0
    n = min(len(actual_read_shares), len(predicted_read_shares))
    errors = [abs(actual_read_shares[i] - predicted_read_shares[i]) * 100.0 for i in range(n)]
    return sum(errors) / n
