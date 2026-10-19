"""Tests for Hearth CLI commands (report, diagnose)."""

import json
from decimal import Decimal
from pathlib import Path

from hearth.cli import main
from hearth.ledger import Ledger


def test_cli_report(tmp_path: Path, capsys: None) -> None:
    ledger_file = tmp_path / "test_ledger.sqlite"
    ledger = Ledger(ledger_file)

    ledger.record_call(
        session_id="test-session-1",
        call_index=1,
        ts_start=100.0,
        ts_end=101.0,
        provider="gemini",
        model="gemini-2.5-flash",
        mode="safe",
        read_tokens=4000,
        write_tokens=0,
        uncached_tokens=1000,
        output_tokens=200,
        cost_usd=Decimal("0.00021"),
    )

    exit_code = main(["report", "--session", "test-session-1", "--ledger", str(ledger_file)])
    assert exit_code == 0


def test_cli_diagnose(tmp_path: Path) -> None:
    trace_file = tmp_path / "diag.jsonl"
    entry = {
        "v": 1,
        "session": "diag-sess",
        "call": 2,
        "usage": {"read": 0, "write": 3000, "uncached": 0},
        "breaks": [
            {
                "cause": "volatile_in_prefix",
                "level": "system",
                "details": "Timestamp in system prompt",
            }
        ],
    }
    trace_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    exit_code = main(["diagnose", str(trace_file)])
    assert exit_code == 0
