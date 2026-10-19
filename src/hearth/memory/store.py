"""SQLite facts store and temporal superseding model for Hearth memory (BUILD_HANDBOOK §5.7, INV-12)."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import hearth
from hearth.memory.checks import validate_fact_write


@dataclass
class Fact:
    id: int
    scope: str
    subject: str
    predicate: str
    value: str
    valid_from: str
    valid_to: str | None
    superseded_by: int | None
    source: str
    source_session: str | None
    tainted: bool
    created_at: str


class MemoryStore:
    """Manages long-term structured facts with temporal validity and superseding (INV-12)."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            hearth_dir = os.environ.get("HEARTH_HOME", os.path.expanduser("~/.hearth"))
            self.db_path = Path(hearth_dir) / "memory.sqlite"
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        # Session pinning snapshot cache to ensure mid-session writes never mutate current SESSION prefix (INV-12)
        self._session_snapshots: dict[str, str] = {}

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    value TEXT NOT NULL,
                    valid_from TEXT NOT NULL,
                    valid_to TEXT,
                    superseded_by INTEGER,
                    source TEXT NOT NULL,
                    source_session TEXT,
                    tainted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_facts_scope_subj ON facts(scope, subject, predicate);"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(scope, valid_to);")

            # Create FTS5 table if supported
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
                        fact_id UNINDEXED,
                        scope,
                        subject,
                        predicate,
                        value
                    );
                    """
                )
            except sqlite3.OperationalError:
                pass  # Fallback to standard SQL query if FTS5 is not compiled in SQLite

    def remember(
        self,
        scope: str,
        subject: str,
        predicate: str,
        value: str,
        source: str = "user",
        source_session: str | None = None,
        tainted: bool = False,
    ) -> int:
        """Store a new fact, superseding any prior active fact for the same scope, subject, and predicate."""
        validate_fact_write(value)

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            # Check for existing active fact
            cur = conn.execute(
                """
                SELECT id FROM facts
                WHERE scope = ? AND subject = ? AND predicate = ? AND valid_to IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                (scope, subject, predicate),
            )
            row = cur.fetchone()
            old_fact_id = row["id"] if row else None

            # Insert new fact
            ins_cur = conn.execute(
                """
                INSERT INTO facts (
                    scope, subject, predicate, value, valid_from, valid_to,
                    superseded_by, source, source_session, tainted, created_at
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    scope,
                    subject,
                    predicate,
                    value,
                    now_iso,
                    source,
                    source_session,
                    1 if tainted else 0,
                    now_iso,
                ),
            )
            new_fact_id = int(ins_cur.lastrowid or 0)

            # Supersede old fact: set valid_to and superseded_by
            if old_fact_id is not None:
                conn.execute(
                    "UPDATE facts SET valid_to = ?, superseded_by = ? WHERE id = ?",
                    (now_iso, new_fact_id, old_fact_id),
                )

            # Sync with FTS table
            try:
                conn.execute(
                    "INSERT INTO facts_fts (fact_id, scope, subject, predicate, value) VALUES (?, ?, ?, ?, ?)",
                    (str(new_fact_id), scope, subject, predicate, value),
                )
            except sqlite3.OperationalError:
                pass

        # If writing mid-session, attach volatile note to current session so turn tail reflects it
        # without mutating the static SESSION prefix segment
        curr_session = hearth.get_current_session()
        if curr_session is not None:
            curr_session.volatile(f"[Memory Updated: {subject} {predicate} {value}]")

        return new_fact_id

    def get_fact(self, fact_id: int) -> Fact | None:
        """Retrieve a fact record by its ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Fact(
                id=row["id"],
                scope=row["scope"],
                subject=row["subject"],
                predicate=row["predicate"],
                value=row["value"],
                valid_from=row["valid_from"],
                valid_to=row["valid_to"],
                superseded_by=row["superseded_by"],
                source=row["source"],
                source_session=row["source_session"],
                tainted=bool(row["tainted"]),
                created_at=row["created_at"],
            )

    def recall(self, scope: str, query: str, k: int = 5) -> list[Fact]:
        """Recall active, non-superseded facts matching query keywords in scope."""
        with self._get_connection() as conn:
            # Try FTS5 search
            facts: list[Fact] = []
            try:
                sanitized_query = "".join(c for c in query if c.isalnum() or c.isspace()).strip()
                if sanitized_query:
                    match_expr = " OR ".join(sanitized_query.split())
                    cur = conn.execute(
                        """
                        SELECT f.* FROM facts f
                        JOIN facts_fts ON facts_fts.fact_id = f.id
                        WHERE f.scope = ? AND f.valid_to IS NULL AND facts_fts MATCH ?
                        ORDER BY f.id DESC LIMIT ?
                        """,
                        (scope, match_expr, k),
                    )
                    for row in cur.fetchall():
                        facts.append(
                            Fact(
                                id=row["id"],
                                scope=row["scope"],
                                subject=row["subject"],
                                predicate=row["predicate"],
                                value=row["value"],
                                valid_from=row["valid_from"],
                                valid_to=row["valid_to"],
                                superseded_by=row["superseded_by"],
                                source=row["source"],
                                source_session=row["source_session"],
                                tainted=bool(row["tainted"]),
                                created_at=row["created_at"],
                            )
                        )
                    if facts:
                        return facts
            except sqlite3.OperationalError:
                pass

            # Fallback to standard LIKE filter
            cur = conn.execute(
                """
                SELECT * FROM facts
                WHERE scope = ? AND valid_to IS NULL
                  AND (subject LIKE ? OR predicate LIKE ? OR value LIKE ?)
                ORDER BY id DESC LIMIT ?
                """,
                (scope, f"%{query}%", f"%{query}%", f"%{query}%", k),
            )
            for row in cur.fetchall():
                facts.append(
                    Fact(
                        id=row["id"],
                        scope=row["scope"],
                        subject=row["subject"],
                        predicate=row["predicate"],
                        value=row["value"],
                        valid_from=row["valid_from"],
                        valid_to=row["valid_to"],
                        superseded_by=row["superseded_by"],
                        source=row["source"],
                        source_session=row["source_session"],
                        tainted=bool(row["tainted"]),
                        created_at=row["created_at"],
                    )
                )
            return facts

    def pin(self, scope: str, subjects: list[str]) -> list[Fact]:
        """Retrieve active facts pinned for a session start."""
        if not subjects:
            return []
        placeholders = ",".join("?" for _ in subjects)
        with self._get_connection() as conn:
            cur = conn.execute(
                f"""
                SELECT * FROM facts
                WHERE scope = ? AND valid_to IS NULL AND subject IN ({placeholders})
                ORDER BY subject ASC, id ASC
                """,
                [scope, *subjects],
            )
            facts = []
            for row in cur.fetchall():
                facts.append(
                    Fact(
                        id=row["id"],
                        scope=row["scope"],
                        subject=row["subject"],
                        predicate=row["predicate"],
                        value=row["value"],
                        valid_from=row["valid_from"],
                        valid_to=row["valid_to"],
                        superseded_by=row["superseded_by"],
                        source=row["source"],
                        source_session=row["source_session"],
                        tainted=bool(row["tainted"]),
                        created_at=row["created_at"],
                    )
                )
            return facts

    def get_pinned_session_text(
        self, scope: str, subjects: list[str], session_id: str | None = None
    ) -> str:
        """Render pinned session facts.

        If session_id is provided or an active session is in context, caches the initial render so mid-session writes
        never mutate the SESSION prefix segment during the active session (INV-12).
        """
        if session_id is None:
            curr = hearth.get_current_session()
            if curr is not None:
                session_id = curr.session_id

        if session_id and session_id in self._session_snapshots:
            return self._session_snapshots[session_id]

        facts = self.pin(scope=scope, subjects=subjects)
        if not facts:
            rendered = ""
        else:
            lines = [f"- {f.subject} {f.predicate} {f.value}" for f in facts]
            rendered = "Session pinned facts:\n" + "\n".join(lines)

        if session_id:
            self._session_snapshots[session_id] = rendered

        return rendered
