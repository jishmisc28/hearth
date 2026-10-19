"""Bench runner module."""

from __future__ import annotations

import argparse
import json
import sys

from bench.m0.runner import run_m0_kill_test


def main() -> None:
    parser = argparse.ArgumentParser(description="Hearth Benchmark Runner")
    parser.add_argument("--m0", action="store_true", help="Run M0 kill test suite")
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
    else:
        print("Hearth Benchmark Runner: specify --m0 to run kill test.")


if __name__ == "__main__":
    main()
