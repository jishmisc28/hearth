"""Hearth command-line interface (BUILD_HANDBOOK §6.2)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from hearth.ledger import Ledger


def cmd_report(args: argparse.Namespace) -> int:
    """Generate session summary report."""
    session_id = args.session
    ledger_path = args.ledger
    ledger = Ledger(ledger_path)

    summary = ledger.get_session_summary(session_id)
    if not summary:
        print(f"Error: No records found for session '{session_id}' in ledger.")
        return 1

    tot_calls = summary["total_calls"]
    tot_in = summary["total_input"]
    tot_read = summary["total_read"]
    tot_write = summary["total_write"]
    tot_uncached = summary["total_uncached"]
    tot_out = summary["total_output"]
    cost_usd = summary["cost_usd"]
    read_share_pct = summary["read_share"] * 100.0

    # Read trace to print breaks if trace exists
    hearth_dir = os.environ.get("HEARTH_HOME", os.path.expanduser("~/.hearth"))
    trace_path = Path(hearth_dir) / "traces" / f"{session_id}.jsonl"

    breaks_list: list[dict[str, Any]] = []
    changes_list: list[dict[str, Any]] = []
    if trace_path.exists():
        with open(trace_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    call_entry = json.loads(line)
                    c_num = call_entry.get("call", 1)
                    for b in call_entry.get("breaks", []):
                        b["call"] = c_num
                        breaks_list.append(b)
                    for ch in call_entry.get("changes", []):
                        ch["call"] = c_num
                        changes_list.append(ch)

    print(f"\nSession Report: {session_id}")
    print(
        f"calls {tot_calls} · input {tot_in:,} tok · read {tot_read:,} ({read_share_pct:.1f}%) · written {tot_write:,} · uncached {tot_uncached:,} · output {tot_out:,}"
    )
    print(f"total cost: ${cost_usd} USD")

    if changes_list:
        print(f"\ntransformations ({len(changes_list)}):")
        for ch in changes_list:
            c = ch.get("call", "?")
            kind = ch.get("kind", "unknown")
            desc = ch.get("details", "") or ch.get("description", "")
            print(f"  call {c:<4} {kind:<22} {desc}")

    if breaks_list:
        print(f"\nprefix breaks ({len(breaks_list)}):")
        for b in breaks_list:
            c = b.get("call", "?")
            cause = b.get("cause", "unknown")
            details = b.get("details", "")
            print(f"  call {c:<4} {cause:<20} {details}")
    else:
        print("\nprefix breaks: 0 (perfect prefix stability)")

    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    """Diagnose cache breaks in a JSONL trace file."""
    trace_path = Path(args.trace_file)
    if not trace_path.exists():
        print(f"Error: Trace file '{trace_path}' does not exist.")
        return 1

    calls: list[dict[str, Any]] = []
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                calls.append(json.loads(line))

    if not calls:
        print(f"Trace file '{trace_path}' is empty.")
        return 1

    tot_in = sum(
        c.get("usage", {}).get("read", 0)
        + c.get("usage", {}).get("write", 0)
        + c.get("usage", {}).get("uncached", 0)
        for c in calls
    )
    tot_read = sum(c.get("usage", {}).get("read", 0) for c in calls)
    read_share = (tot_read / tot_in * 100.0) if tot_in > 0 else 0.0

    session_name = calls[0].get("session", trace_path.stem)
    print(
        f"\nDiagnosing trace: {trace_path.name} (session '{session_name}') · read share {read_share:.1f}%"
    )

    found_breaks = False
    for c in calls:
        call_num = c.get("call", 1)
        for b in c.get("breaks", []):
            found_breaks = True
            cause = b.get("cause", "")
            level = b.get("level", "")
            details = b.get("details", "")
            print(f"  call {call_num}: level {level} · cause {cause}")
            print(f"    detail: {details}")
            if cause == "volatile_in_prefix":
                print(
                    "    fix: relocate dynamic values to tail with hearth.volatile(...) or mode='optimize'"
                )
            elif cause == "tools_reordered":
                print("    fix: mode='safe' will restore first-seen tool order automatically")
            elif cause == "below_minimum":
                print("    note: prefix below provider caching threshold")

    if not found_breaks:
        print("  No prefix breaks diagnosed in this trace.")

    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    """Replay session trace through simulator under observe, safe, and optimize modes."""
    from hearth.replay import format_replay_table, replay_trace_file

    trace_file = Path(args.trace_file)
    if not trace_file.exists():
        print(f"Error: Trace file '{trace_file}' does not exist.")
        return 1

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    provider = getattr(args, "provider", "gemini")
    model = getattr(args, "model", "gemini-2.5-flash")

    summaries = replay_trace_file(
        trace_path=trace_file,
        modes=modes,
        provider=provider,
        model=model,
    )
    print(format_replay_table(summaries))
    return 0


def cmd_guard(args: argparse.Namespace) -> int:
    """Run tests and check for regression in prefix cache stability against baseline."""
    import subprocess
    import tempfile

    baseline_path = Path(args.baseline) if args.baseline else None
    run_cmd = args.run

    with tempfile.TemporaryDirectory() as tmp_dir:
        env = dict(os.environ)
        env["HEARTH_TRACE_DIR"] = tmp_dir
        print(f"[Hearth Guard] Executing test suite: {run_cmd}")
        res = subprocess.run(run_cmd, shell=True, env=env)
        if res.returncode != 0:
            print(f"[Hearth Guard] Command failed with exit code {res.returncode}")
            return res.returncode

        # Collect user-caused breaks from newly generated traces
        new_breaks: list[dict[str, Any]] = []
        for trace_file in Path(tmp_dir).glob("*.jsonl"):
            with open(trace_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        call = json.loads(line)
                        for b in call.get("breaks", []):
                            if b.get("user_caused", True):
                                new_breaks.append(b)

        # Collect baseline breaks
        baseline_breaks: list[dict[str, Any]] = []
        if baseline_path and baseline_path.exists():
            base_files = (
                [baseline_path] if baseline_path.is_file() else list(baseline_path.glob("*.jsonl"))
            )
            for trace_file in base_files:
                with open(trace_file, encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            call = json.loads(line)
                            for b in call.get("breaks", []):
                                if b.get("user_caused", True):
                                    baseline_breaks.append(b)

        # Check for regressions
        if len(new_breaks) > len(baseline_breaks):
            print(
                f"\n[Hearth Guard FAILED] Detected {len(new_breaks)} user-caused prefix breaks (baseline had {len(baseline_breaks)}):"
            )
            for b in new_breaks:
                print(
                    f"  cause: {b.get('cause')} · level: {b.get('level')} · details: {b.get('details')}"
                )
            return 1

        print(
            f"\n[Hearth Guard PASSED] All sessions verified. {len(new_breaks)} user-caused breaks detected."
        )
        return 0


def cmd_bench(args: argparse.Namespace) -> int:
    """Run benchmark suite and generate Cache Efficiency Report."""
    from bench.m4.runner import run_m4_benchmark

    summary = run_m4_benchmark()
    if args.report:
        print(f"\n[Cache Efficiency Report generated and frozen at {summary.get('report_file')}]")
        print(f"Overall Cost Reduction: {summary.get('overall_savings_pct')}%")
        print(f"Calibration MAE: {summary.get('calibration_holdout_mae_points')} points")
    return 0 if summary.get("gate_verified", False) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hearth", description="Hearth context engine CLI")
    subparsers = parser.add_subparsers(dest="command")

    # report
    p_report = subparsers.add_parser(
        "report", help="Report prompt caching performance for a session"
    )
    p_report.add_argument("--session", required=True, help="Session ID to report")
    p_report.add_argument("--ledger", default=None, help="Path to SQLite ledger file")

    # diagnose
    p_diagnose = subparsers.add_parser("diagnose", help="Diagnose cache breaks in a trace file")
    p_diagnose.add_argument("trace_file", help="Path to session .jsonl trace file")

    # replay
    p_replay = subparsers.add_parser(
        "replay", help="Replay session trace through simulator across modes"
    )
    p_replay.add_argument("trace_file", help="Path to session .jsonl trace file")
    p_replay.add_argument(
        "--modes",
        default="observe,safe,optimize",
        help="Comma-separated modes to replay (default: observe,safe,optimize)",
    )
    p_replay.add_argument("--provider", default="gemini", help="Provider to simulate")
    p_replay.add_argument("--model", default="gemini-2.5-flash", help="Model to simulate")

    # guard
    p_guard = subparsers.add_parser("guard", help="Check test runs against baseline cache breaks")
    p_guard.add_argument("--baseline", default=None, help="Directory or file with baseline traces")
    p_guard.add_argument("--run", required=True, help="Command to run agent test suite")

    # bench
    p_bench = subparsers.add_parser("bench", help="Run benchmark suite")
    p_bench.add_argument(
        "--report", action="store_true", help="Generate/freeze Cache Efficiency Report"
    )

    args = parser.parse_args(argv)

    if args.command == "report":
        return cmd_report(args)
    elif args.command == "diagnose":
        return cmd_diagnose(args)
    elif args.command == "replay":
        return cmd_replay(args)
    elif args.command == "guard":
        return cmd_guard(args)
    elif args.command == "bench":
        return cmd_bench(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
