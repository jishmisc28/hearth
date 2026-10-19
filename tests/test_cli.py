import json
from decimal import Decimal
from pathlib import Path
from typing import Any

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


def test_cli_replay(tmp_path: Path, capsys: Any) -> None:
    trace_file = tmp_path / "replay_test.jsonl"
    system_text = "Instructions: " + ("You are a helpful software assistant. " * 150)
    calls = [
        {
            "v": 1,
            "session": "replay-sess",
            "call": 1,
            "ts": 100.0,
            "request": {
                "kwargs": {
                    "model": "gemini-2.5-flash",
                    "system": system_text,
                    "messages": [{"role": "user", "content": "Question 1"}],
                }
            },
        },
        {
            "v": 1,
            "session": "replay-sess",
            "call": 2,
            "ts": 110.0,
            "request": {
                "kwargs": {
                    "model": "gemini-2.5-flash",
                    "system": system_text,
                    "messages": [
                        {"role": "user", "content": "Question 1"},
                        {"role": "assistant", "content": "Answer 1"},
                        {"role": "user", "content": "Question 2"},
                    ],
                }
            },
        },
        {
            "v": 1,
            "session": "replay-sess",
            "call": 3,
            "ts": 120.0,
            "request": {
                "kwargs": {
                    "model": "gemini-2.5-flash",
                    "system": f"Current time: 2026-10-19T14:00:00Z\n{system_text}",
                    "messages": [
                        {"role": "user", "content": "Question 1"},
                        {"role": "assistant", "content": "Answer 1"},
                        {"role": "user", "content": "Question 2"},
                        {"role": "assistant", "content": "Answer 2"},
                        {"role": "user", "content": "Question 3"},
                    ],
                }
            },
        },
    ]
    with open(trace_file, "w", encoding="utf-8") as f:
        for c in calls:
            f.write(json.dumps(c) + "\n")

    exit_code = main(["replay", str(trace_file), "--modes", "observe,safe,optimize"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "observe" in captured.out
    assert "safe" in captured.out
    assert "optimize" in captured.out


def test_cli_guard(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir()
    clean_trace = baseline_dir / "clean.jsonl"
    clean_trace.write_text(
        json.dumps(
            {
                "call": 1,
                "breaks": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # 1. Clean run passes
    exit_code = main(["guard", "--baseline", str(baseline_dir), "--run", "true"])
    assert exit_code == 0
