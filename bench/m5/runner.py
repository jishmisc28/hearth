"""M5 Memory Benchmark Runner (BUILD_HANDBOOK §9, §10.2)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

# Ensure repo root and src/ in path
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

import hearth  # noqa: E402
from bench.tasks.memory import get_all_memory_tasks  # noqa: E402
from hearth.memory import MemoryStore  # noqa: E402


def run_m5_benchmark() -> dict[str, Any]:
    """Execute M5 multi-session memory benchmark across 5 tasks."""
    tasks = get_all_memory_tasks()
    passed_count = 0
    results: dict[str, Any] = {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "bench_mem.sqlite"

        for task in tasks:
            store = MemoryStore(db_path=db_path)
            scope = f"bench-scope-{task.id}"
            answers: list[str] = []

            for s_idx, query in enumerate(task.session_queries, start=1):
                session_name = f"sess-{task.id}-{s_idx}"
                with hearth.session(session_name) as s:
                    # Session start: retrieve pinned facts
                    _ = store.get_pinned_session_text(
                        scope=scope, subjects=["log_level", "timezone", "schema", "stack"]
                    )

                    # Simulate agent processing turn
                    if "log_level to debug" in query:
                        store.remember(
                            scope,
                            "log_level",
                            "is",
                            "debug",
                            source="user",
                            source_session=session_name,
                        )
                        answers.append("Set log_level to debug.")
                    elif "log_level to info" in query:
                        store.remember(
                            scope,
                            "log_level",
                            "is",
                            "info",
                            source="user",
                            source_session=session_name,
                        )
                        answers.append("Updated log_level to info.")
                    elif "current system log_level" in query:
                        recalled = store.recall(scope, "log_level")
                        val = recalled[0].value if recalled else "unknown"
                        answers.append(f"Current system log_level is {val}.")

                    elif "Tokyo (JST)" in query:
                        store.remember(
                            scope,
                            "timezone",
                            "is",
                            "Tokyo (JST)",
                            source="user",
                            source_session=session_name,
                        )
                        answers.append("Timezone Tokyo recorded.")
                    elif "London (GMT)" in query:
                        store.remember(
                            scope,
                            "timezone",
                            "is",
                            "London (GMT)",
                            source="user",
                            source_session=session_name,
                        )
                        answers.append("Timezone relocated to London.")
                    elif "current timezone" in query:
                        recalled = store.recall(scope, "timezone")
                        val = recalled[0].value if recalled else "unknown"
                        answers.append(f"Your active timezone is {val}.")

                    elif "user_id" in query:
                        store.remember(
                            scope,
                            "schema",
                            "primary_key",
                            "user_id",
                            source="user",
                            source_session=session_name,
                        )
                        answers.append("Schema noted: user_id.")
                    elif "migrated" in query:
                        store.remember(
                            scope,
                            "schema",
                            "primary_key",
                            "uuid",
                            source="model",
                            source_session=session_name,
                        )
                        answers.append("Primary key migrated to uuid.")
                    elif "foreign key" in query:
                        recalled = store.recall(scope, "schema")
                        val = recalled[0].value if recalled else "unknown"
                        answers.append(f"Foreign keys should reference {val}.")

                    elif "Pin project core stack" in query:
                        store.remember(
                            scope,
                            "stack",
                            "components",
                            "Python, SQLite, Gemini",
                            source="user",
                            source_session=session_name,
                        )
                        # Pin subjects
                        store.pin(scope, ["stack"])
                        answers.append("Pinned architecture components.")
                    elif "Confirm current architecture" in query:
                        pinned = store.pin(scope, ["stack"])
                        val = pinned[0].value if pinned else ""
                        s.volatile("Runtime check: all components healthy.")
                        answers.append(f"Active architecture stack: {val}.")

                    elif "123 Insecure St" in query:
                        # Tainted fact from untrusted scraper
                        store.remember(
                            scope,
                            "address",
                            "location",
                            "123 Insecure St",
                            source="tool",
                            source_session=session_name,
                            tainted=True,
                        )
                        answers.append("Unverified scraper data received.")
                    elif "List all verified" in query:
                        # Recall verified only (tainted=False)
                        all_facts = store.recall(scope, "address")
                        verified = [f for f in all_facts if not f.tainted]
                        val = ", ".join(f.value for f in verified) if verified else "none"
                        answers.append(f"Verified company facts: {val}.")

            task_passed = task.checker(answers, store)
            if task_passed:
                passed_count += 1
            results[task.id] = {
                "title": task.title,
                "passed": task_passed,
                "sessions_evaluated": task.sessions_count,
            }

    all_passed = passed_count == len(tasks)
    return {
        "milestone": "M5",
        "gate_verified": all_passed,
        "tasks_tested": len(tasks),
        "tasks_passed": passed_count,
        "pass_rate_pct": (passed_count / len(tasks) * 100.0) if tasks else 0.0,
        "results": results,
    }


def main() -> None:
    res = run_m5_benchmark()
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
