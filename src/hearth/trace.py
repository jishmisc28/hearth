"""Trace writer and ledger record structures."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class TraceRecorder:
    """Writes JSONL traces for Hearth sessions."""

    def __init__(self, trace_dir: str | Path | None = None):
        if trace_dir is None:
            hearth_dir = os.environ.get("HEARTH_HOME", os.path.expanduser("~/.hearth"))
            self.trace_dir = Path(hearth_dir) / "traces"
        else:
            self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def record_call(
        self,
        *,
        session_id: str,
        call_index: int,
        ts_start: float,
        ts_end: float,
        ts_first_token: float | None = None,
        provider: str,
        api: str,
        model: str,
        mode: str,
        params: dict[str, Any] | None = None,
        fingerprints: dict[str, list[str]] | None = None,
        usage: dict[str, Any] | None = None,
        breaks: list[dict[str, Any]] | None = None,
        changes: list[dict[str, Any]] | None = None,
        body: dict[str, Any] | None = None,
        record_body: bool = False,
    ) -> dict[str, Any]:
        """Record a single API call trace.

        Enforces INV-09: request and response bodies are omitted unless record_body is True.
        """
        trace_path = self.trace_dir / f"{session_id}.jsonl"

        entry: dict[str, Any] = {
            "v": 1,
            "session": session_id,
            "call": call_index,
            "ts_start": ts_start,
            "ts_first_token": ts_first_token,
            "ts_end": ts_end,
            "provider": provider,
            "api": api,
            "model": model,
            "mode": mode,
            "params": params or {},
            "fingerprints": fingerprints or {"tools": [], "system": [], "messages": []},
            "usage": usage
            or {
                "raw": {},
                "read": 0,
                "write": 0,
                "uncached": 0,
                "output": 0,
            },
            "breaks": breaks or [],
            "changes": changes or [],
        }

        # INV-09: No prompt content in trace unless record_body=True
        if record_body and body is not None:
            entry["body"] = body

        with open(trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def read_session(self, session_id: str) -> list[dict[str, Any]]:
        """Read all trace entries recorded for a session."""
        trace_path = self.trace_dir / f"{session_id}.jsonl"
        if not trace_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with open(trace_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries


_default_recorder: TraceRecorder | None = None


def get_trace_recorder(trace_dir: str | Path | None = None) -> TraceRecorder:
    global _default_recorder
    if trace_dir is not None:
        return TraceRecorder(trace_dir)
    if _default_recorder is None:
        _default_recorder = TraceRecorder()
    return _default_recorder
