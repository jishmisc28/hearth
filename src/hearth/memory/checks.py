"""Write checks and safety guards for Hearth memory (BUILD_HANDBOOK §5.7, M5)."""

from __future__ import annotations

import re

# Secret pattern detectors
SECRETS_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),  # API keys
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),  # Google API key
    re.compile(r"ghp_[0-9a-zA-Z]{36}"),  # GitHub Personal Access Token
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS Access Key ID
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),  # Private keys
]

# Instruction override / prompt injection patterns
INJECTION_PATTERNS = [
    re.compile(r"\bignore\s+previous\b", re.IGNORECASE),
    re.compile(r"\bfrom\s+now\s+on\b", re.IGNORECASE),
    re.compile(r"\balways\s+(?:cc|forward|send)\b", re.IGNORECASE),
    re.compile(r"\bdisregard\s+prior\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+override\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
]

MAX_FACT_VALUE_LENGTH = 2000


class MemoryWriteError(ValueError):
    """Raised when a memory fact fails safety or size write checks."""

    pass


def validate_fact_write(value: str) -> None:
    """Validate fact value against size, secrets, and instruction-injection rules (BUILD_HANDBOOK §5.7)."""
    # 1. Size check
    if len(value) > MAX_FACT_VALUE_LENGTH:
        raise MemoryWriteError(
            f"Fact value exceeds maximum length of {MAX_FACT_VALUE_LENGTH} characters (got {len(value)})"
        )

    # 2. Secret check
    for pat in SECRETS_PATTERNS:
        if pat.search(value):
            raise MemoryWriteError("Fact value rejected: contains sensitive secret or credentials")

    # 3. Instruction-like text check
    for pat in INJECTION_PATTERNS:
        if pat.search(value):
            raise MemoryWriteError(
                "Fact value rejected: contains prompt injection or override instruction"
            )
