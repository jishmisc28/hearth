"""Verify that all invariant tests specified in BUILD_HANDBOOK section 8 exist."""

import importlib
import inspect
from pathlib import Path

# Invariants specified in BUILD_HANDBOOK §8
EXPECTED_NAMED_TESTS = [
    "test_observe_passthrough_bytes",  # INV-01 (M0)
    "test_safe_no_content_change",  # INV-02 (M1)
    "test_fingerprint_determinism",  # INV-03 (M1)
    "test_append_only",  # INV-04 (M1)
    "test_changes_reported",  # INV-05 (M2)
    "test_usage_reconciles_anthropic",  # INV-06 (M1)
    "test_usage_reconciles_openai",  # INV-06 (M1)
    "test_usage_reconciles_gemini",  # INV-06 (M2)
    "test_fail_open",  # INV-07 (M1)
    "test_no_extra_network",  # INV-08 (M1)
    "test_no_content_by_default",  # INV-09 (M0)
    "test_break_attribution",  # INV-10 (M1)
    "test_planner_limits",  # INV-11 (M1)
    "test_memory_supersede",  # INV-12 (M5)
    "test_memory_no_session_mutation",  # INV-12 (M5)
    "test_cost_decimal",  # INV-13 (M1)
]


def test_all_named_invariant_tests_exist() -> None:
    """Check that every test function named in BUILD_HANDBOOK section 8 exists in tests/."""
    tests_dir = Path(__file__).parent
    found_tests: set[str] = set()

    for py_file in tests_dir.glob("test_*.py"):
        if py_file.name == Path(__file__).name:
            continue
        try:
            mod = importlib.import_module(f"tests.{py_file.stem}")
        except Exception:
            try:
                mod = importlib.import_module(py_file.stem)
            except Exception as e:
                print(f"Failed to import {py_file}: {e}")
                continue

        for name, obj in inspect.getmembers(mod):
            if name.startswith("test_") and callable(obj):
                found_tests.add(name)

    missing = [test_name for test_name in EXPECTED_NAMED_TESTS if test_name not in found_tests]
    assert not missing, f"Missing required named tests from BUILD_HANDBOOK §8: {missing}"
