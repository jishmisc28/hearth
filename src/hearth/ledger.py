"""SQLite summary ledger for session and call metrics (BUILD_HANDBOOK §4.1, INV-09)."""

from __future__ import annotations

import os
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any


class Ledger:
    """Manages SQLite storage of session and call cache performance metrics."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            hearth_dir = os.environ.get("HEARTH_HOME", os.path.expanduser("~/.hearth"))
            self.db_path = Path(hearth_dir) / "ledger.sqlite"
        else:
            self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    total_calls INTEGER NOT NULL DEFAULT 0,
                    total_input INTEGER NOT NULL DEFAULT 0,
                    total_read INTEGER NOT NULL DEFAULT 0,
                    total_write INTEGER NOT NULL DEFAULT 0,
                    total_uncached INTEGER NOT NULL DEFAULT 0,
                    total_output INTEGER NOT NULL DEFAULT 0,
                    cost_usd TEXT NOT NULL DEFAULT '0.0',
                    read_share REAL NOT NULL DEFAULT 0.0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    call_index INTEGER NOT NULL,
                    ts_start REAL NOT NULL,
                    ts_end REAL NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    read_tokens INTEGER NOT NULL,
                    write_tokens INTEGER NOT NULL,
                    uncached_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cost_usd TEXT NOT NULL,
                    breaks_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                )
                """
            )
            conn.commit()

    def record_call(
        self,
        *,
        session_id: str,
        call_index: int,
        ts_start: float,
        ts_end: float,
        provider: str,
        model: str,
        mode: str,
        read_tokens: int,
        write_tokens: int,
        uncached_tokens: int,
        output_tokens: int,
        cost_usd: Decimal,
        breaks_count: int = 0,
    ) -> None:
        """Record call summary into SQLite ledger without prompt content (INV-09)."""
        tot_in = read_tokens + write_tokens + uncached_tokens
        with self._get_connection() as conn:
            # 1. Insert call record
            conn.execute(
                """
                INSERT INTO calls (
                    session_id, call_index, ts_start, ts_end, provider, model, mode,
                    read_tokens, write_tokens, uncached_tokens, output_tokens, cost_usd, breaks_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    call_index,
                    ts_start,
                    ts_end,
                    provider,
                    model,
                    mode,
                    read_tokens,
                    write_tokens,
                    uncached_tokens,
                    output_tokens,
                    str(cost_usd),
                    breaks_count,
                ),
            )

            # 2. Update or insert session summary
            cur = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            if row is None:
                r_share = float(read_tokens) / tot_in if tot_in > 0 else 0.0
                conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id, created_at, total_calls, total_input, total_read,
                        total_write, total_uncached, total_output, cost_usd, read_share
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        ts_start,
                        1,
                        tot_in,
                        read_tokens,
                        write_tokens,
                        uncached_tokens,
                        output_tokens,
                        str(cost_usd),
                        r_share,
                    ),
                )
            else:
                new_calls = row["total_calls"] + 1
                new_input = row["total_input"] + tot_in
                new_read = row["total_read"] + read_tokens
                new_write = row["total_write"] + write_tokens
                new_uncached = row["total_uncached"] + uncached_tokens
                new_output = row["total_output"] + output_tokens
                new_cost = str(Decimal(row["cost_usd"]) + cost_usd)
                new_share = float(new_read) / new_input if new_input > 0 else 0.0

                conn.execute(
                    """
                    UPDATE sessions SET
                        total_calls = ?, total_input = ?, total_read = ?,
                        total_write = ?, total_uncached = ?, total_output = ?,
                        cost_usd = ?, read_share = ?
                    WHERE session_id = ?
                    """,
                    (
                        new_calls,
                        new_input,
                        new_read,
                        new_write,
                        new_uncached,
                        new_output,
                        new_cost,
                        new_share,
                        session_id,
                    ),
                )
            conn.commit()

    def get_session_summary(self, session_id: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cur.fetchone()
            if row is None:
                return None
            return dict(row)
