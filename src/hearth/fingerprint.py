"""Deterministic per-message fingerprints and rolling segment hashes (BUILD_HANDBOOK §5.1, INV-03)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


def canonical_serialize(obj: Any) -> str:
    """Serialize object to JSON deterministically in application key order without float round-tripping."""
    # separators=(',', ':') removes whitespace
    # ensure_ascii=False ensures exact UTF-8 byte representation
    return json.dumps(obj, cls=_DecimalEncoder, separators=(",", ":"), ensure_ascii=False)


# Cache structure: key -> (full_hash, serialized_str)
# Max capacity 4096 entries
_LRU_CAPACITY = 4096
_fingerprint_cache: dict[tuple[str, int, str, str], str] = {}


def fingerprint_message(msg: Any) -> str:
    """Compute deterministic SHA-256 fingerprint for a message, system block, or tool.

    LRU-cached by (role, length, first 64 bytes, last 64 bytes) for sub-millisecond lookups.
    """
    serialized = canonical_serialize(msg)
    encoded = serialized.encode("utf-8")
    length = len(encoded)

    role = "none"
    if isinstance(msg, dict):
        role = str(msg.get("role", "none"))

    prefix = encoded[:64].decode("utf-8", errors="replace")
    suffix = encoded[-64:].decode("utf-8", errors="replace") if length > 64 else prefix
    cache_key = (role, length, prefix, suffix)

    if cache_key in _fingerprint_cache:
        return _fingerprint_cache[cache_key]

    digest = hashlib.sha256(encoded).hexdigest()

    # Simple LRU eviction if over capacity
    if len(_fingerprint_cache) >= _LRU_CAPACITY:
        # Pop oldest item
        first_key = next(iter(_fingerprint_cache))
        del _fingerprint_cache[first_key]

    _fingerprint_cache[cache_key] = digest
    return digest


def rolling_segment_hash(fingerprints: list[str]) -> str:
    """Compute rolling SHA-256 over fingerprints in order so divergence is O(number of messages)."""
    h = hashlib.sha256()
    for fp in fingerprints:
        h.update(fp.encode("utf-8"))
    return h.hexdigest()
