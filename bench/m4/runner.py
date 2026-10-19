"""M4 Benchmark Runner (BUILD_HANDBOOK §10.2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ensure repo root and src/ in path
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from bench.m4.freeze_report import generate_cache_efficiency_report  # noqa: E402


def run_m4_benchmark() -> dict[str, Any]:
    """Execute M4 benchmark and return summary dictionary."""
    return generate_cache_efficiency_report()


def main() -> None:
    res = run_m4_benchmark()
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
