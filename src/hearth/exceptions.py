"""Exception types for Hearth."""

from __future__ import annotations


class HearthError(Exception):
    """Base exception for all Hearth errors."""


class HearthPrefixBreak(HearthError):
    """Raised before sending when strict=True and a user-caused prefix break is detected."""

    def __init__(
        self,
        message: str,
        cause: str,
        level: str,
        message_index: int | None = None,
    ):
        super().__init__(message)
        self.cause = cause
        self.level = level
        self.message_index = message_index
