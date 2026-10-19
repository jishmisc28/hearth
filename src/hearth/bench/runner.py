"""Bench runner module."""

from __future__ import annotations

import argparse
import json
import sys

from bench.m0.runner import run_m0_kill_test
from bench.m2.runner import run_m2_benchmark
from bench.m3.runner import run_m3_benchmark
from bench.m4.runner import run_m4_benchmark
from bench.m5.runner import run_m5_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Hearth Benchmark Runner")
    parser.add_argument("--m0", action="store_true", help="Run M0 kill test suite")
    parser.add_argument("--m2", action="store_true", help="Run M2 benchmark suite")
    parser.add_argument("--m3", action="store_true", help="Run M3 benchmark suite")
    parser.add_argument("--m4", action="store_true", help="Run M4 benchmark suite")
    parser.add_argument("--m5", action="store_true", help="Run M5 benchmark suite")
    parser.add_argument(
        "--report", action="store_true", help="Generate/freeze Cache Efficiency Report"
    )
    parser.add_argument("--verify", action="store_true", help="Verify gate conditions")
    args = parser.parse_args()

    if args.m0:
        summary = run_m0_kill_test()
        print("\n" + json.dumps(summary, indent=2))
        if args.verify:
            if "GO" in summary.get("decision", ""):
                print("\n[VERIFICATION PASSED] M0 Kill Test Decision: GO")
                sys.exit(0)
            else:
                print(f"\n[VERIFICATION FAILED] Decision: {summary.get('decision')}")
                sys.exit(1)
    elif args.m2:
        m2_summary = run_m2_benchmark()
        print("\n" + json.dumps(m2_summary, indent=2))
        if args.verify:
            if m2_summary.get("gate_verified", False):
                print("\n[VERIFICATION PASSED] M2 Benchmark Gate: VERIFIED")
                sys.exit(0)
            else:
                print("\n[VERIFICATION FAILED] M2 Benchmark Gate conditions not met")
                sys.exit(1)
    elif args.m3:
        m3_summary = run_m3_benchmark()
        print("\n" + json.dumps(m3_summary, indent=2))
        if args.verify:
            if m3_summary.get("gate_verified", False):
                print("\n[VERIFICATION PASSED] M3 Benchmark Gate: VERIFIED")
                sys.exit(0)
            else:
                print("\n[VERIFICATION FAILED] M3 Benchmark Gate conditions not met")
                sys.exit(1)
    elif args.m4 or args.report:
        m4_summary = run_m4_benchmark()
        print("\n" + json.dumps(m4_summary, indent=2))
        if args.verify:
            if m4_summary.get("gate_verified", False):
                print("\n[VERIFICATION PASSED] M4 Benchmark Gate: VERIFIED")
                sys.exit(0)
            else:
                print("\n[VERIFICATION FAILED] M4 Benchmark Gate conditions not met")
                sys.exit(1)
    elif args.m5:
        m5_summary = run_m5_benchmark()
        print("\n" + json.dumps(m5_summary, indent=2))
        if args.verify:
            if m5_summary.get("gate_verified", False):
                print("\n[VERIFICATION PASSED] M5 Benchmark Gate: VERIFIED")
                sys.exit(0)
            else:
                print("\n[VERIFICATION FAILED] M5 Benchmark Gate conditions not met")
                sys.exit(1)
    else:
        print("Hearth Benchmark Runner: specify --m0, --m2, --m3, --m4, or --m5.")


if __name__ == "__main__":
    main()
