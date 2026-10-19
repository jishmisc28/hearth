"""Prefix guard and break taxonomy (BUILD_HANDBOOK §5.2, INV-10)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from hearth.exceptions import HearthPrefixBreak
from hearth.fingerprint import fingerprint_message

# Taxonomy of cause codes and user attribution (BUILD_HANDBOOK §5.2, INV-10)
# INV-10: below_minimum, short_session, ttl_expired, and provider_miss are NEVER user-caused.
CAUSE_ATTRIBUTION: dict[str, bool] = {
    "below_minimum": False,
    "short_session": False,
    "ttl_expired": False,
    "provider_miss": False,
    "params_changed": True,
    "tools_changed": True,
    "tools_reordered": True,
    "volatile_in_prefix": True,
    "system_changed": True,
    "session_mutated": True,
    "image_toggled": True,
    "history_rewritten": True,
    "no_breakpoints": True,
    "metadata_dropped": False,  # Framework caused
    "cold_subagent": False,  # Design trade-off
}

VOLATILE_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}|git commit|session-|branch)",
    re.IGNORECASE,
)


def is_user_caused(cause: str) -> bool:
    """Return whether a prefix break cause is attributable to user/application code (INV-10)."""
    return CAUSE_ATTRIBUTION.get(cause, False)


@dataclass(frozen=True)
class BreakEvent:
    cause: str
    user_caused: bool
    level: str  # "tools", "system", "messages"
    message_index: int | None
    tokens_rewritten: int
    details: str


def classify_break_cause(
    prev_params: dict[str, Any],
    curr_params: dict[str, Any],
    prev_tools: list[dict[str, Any]],
    curr_tools: list[dict[str, Any]],
    prev_system: str,
    curr_system: str,
    prev_messages: list[dict[str, Any]],
    curr_messages: list[dict[str, Any]],
    total_tokens: int,
    min_prefix_tokens: int,
    time_gap_seconds: float,
    ttl_seconds: float,
    provider_read_tokens: int = 0,
) -> BreakEvent | None:
    """Classifies divergence between calls strictly in precedence order (BUILD_HANDBOOK §5.2)."""
    # 1. below_minimum
    if total_tokens < min_prefix_tokens:
        return BreakEvent(
            cause="below_minimum",
            user_caused=False,
            level="system",
            message_index=None,
            tokens_rewritten=0,
            details=f"Context tokens ({total_tokens}) below provider minimum ({min_prefix_tokens})",
        )

    # 3. ttl_expired
    if time_gap_seconds > ttl_seconds:
        return BreakEvent(
            cause="ttl_expired",
            user_caused=False,
            level="system",
            message_index=None,
            tokens_rewritten=total_tokens,
            details=f"Call gap ({time_gap_seconds:.1f}s) exceeded provider TTL ({ttl_seconds:.1f}s)",
        )

    # 4. provider_miss
    # If prefix was identical and within TTL, but provider reported 0 read
    if (
        prev_params == curr_params
        and prev_tools == curr_tools
        and prev_system == curr_system
        and prev_messages == curr_messages[: len(prev_messages)]
        and provider_read_tokens == 0
        and len(prev_messages) > 0
    ):
        return BreakEvent(
            cause="provider_miss",
            user_caused=False,
            level="system",
            message_index=None,
            tokens_rewritten=total_tokens,
            details="Identical prefix within TTL had 0 cached tokens reported by provider",
        )

    # 5. params_changed
    for k in ("model", "tool_choice", "temperature", "parallel_tool_calls"):
        if prev_params.get(k) != curr_params.get(k):
            return BreakEvent(
                cause="params_changed",
                user_caused=True,
                level="system",
                message_index=None,
                tokens_rewritten=total_tokens,
                details=f"Parameter '{k}' changed from '{prev_params.get(k)}' to '{curr_params.get(k)}'",
            )

    # 6 & 7. tools_changed / tools_reordered
    prev_names = [str(t.get("name", "")) for t in prev_tools]
    curr_names = [str(t.get("name", "")) for t in curr_tools]
    if sorted(prev_names) == sorted(curr_names) and prev_names != curr_names:
        return BreakEvent(
            cause="tools_reordered",
            user_caused=True,
            level="tools",
            message_index=None,
            tokens_rewritten=total_tokens,
            details=f"Tools order changed: {prev_names} -> {curr_names}",
        )
    if prev_tools != curr_tools:
        return BreakEvent(
            cause="tools_changed",
            user_caused=True,
            level="tools",
            message_index=None,
            tokens_rewritten=total_tokens,
            details="Tool definitions or count differed from previous call",
        )

    # 8. volatile_in_prefix
    if prev_system != curr_system:
        if VOLATILE_PATTERN.search(curr_system):
            return BreakEvent(
                cause="volatile_in_prefix",
                user_caused=True,
                level="system",
                message_index=0,
                tokens_rewritten=total_tokens,
                details="Detected volatile timestamp, date, or git hash in system prompt",
            )
        # 9. system_changed
        return BreakEvent(
            cause="system_changed",
            user_caused=True,
            level="system",
            message_index=0,
            tokens_rewritten=total_tokens,
            details="System prompt differed from previous call",
        )

    # 12. history_rewritten
    # Compare common prefix of messages
    for idx, (p_msg, c_msg) in enumerate(zip(prev_messages, curr_messages, strict=False)):
        if fingerprint_message(p_msg) != fingerprint_message(c_msg):
            return BreakEvent(
                cause="history_rewritten",
                user_caused=True,
                level="messages",
                message_index=idx,
                tokens_rewritten=total_tokens,
                details=f"Historical message at index {idx} was modified",
            )

    return None


class PrefixGuard:
    """Tracks session history and verifies prefix stability across consecutive calls."""

    def __init__(
        self, strict: bool = False, min_prefix_tokens: int = 2048, ttl_seconds: float = 3600.0
    ):
        self.strict = strict
        self.min_prefix_tokens = min_prefix_tokens
        self.ttl_seconds = ttl_seconds
        self.prev_params: dict[str, Any] = {}
        self.prev_tools: list[dict[str, Any]] = []
        self.prev_system: str = ""
        self.prev_messages: list[dict[str, Any]] = []
        self.last_ts: float | None = None

    def evaluate_call(
        self,
        curr_params: dict[str, Any],
        curr_tools: list[dict[str, Any]],
        curr_system: str,
        curr_messages: list[dict[str, Any]],
        total_tokens: int,
        ts: float,
        provider_read_tokens: int = 0,
    ) -> BreakEvent | None:
        """Evaluate upcoming call against previous call state."""
        time_gap = (ts - self.last_ts) if self.last_ts is not None else 0.0

        event = None
        if self.prev_messages or self.prev_system or self.prev_tools:
            event = classify_break_cause(
                prev_params=self.prev_params,
                curr_params=curr_params,
                prev_tools=self.prev_tools,
                curr_tools=curr_tools,
                prev_system=self.prev_system,
                curr_system=curr_system,
                prev_messages=self.prev_messages,
                curr_messages=curr_messages,
                total_tokens=total_tokens,
                min_prefix_tokens=self.min_prefix_tokens,
                time_gap_seconds=time_gap,
                ttl_seconds=self.ttl_seconds,
                provider_read_tokens=provider_read_tokens,
            )
        elif total_tokens < self.min_prefix_tokens:
            event = BreakEvent(
                cause="below_minimum",
                user_caused=False,
                level="system",
                message_index=None,
                tokens_rewritten=0,
                details=f"Context tokens ({total_tokens}) below provider minimum ({self.min_prefix_tokens})",
            )

        if event is not None and self.strict and event.user_caused:
            raise HearthPrefixBreak(
                f"Prefix break detected: {event.cause} ({event.details})",
                cause=event.cause,
                level=event.level,
                message_index=event.message_index,
            )

        # Update previous call state
        self.prev_params = dict(curr_params)
        self.prev_tools = list(curr_tools)
        self.prev_system = curr_system
        self.prev_messages = list(curr_messages)
        self.last_ts = ts

        return event
