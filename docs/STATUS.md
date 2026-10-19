# Status

Newest first. Format in `CLAUDE.md`. The GTM thread decides what can be claimed from this file, `docs/BENCH.md` and `docs/REPORT.md` only.

| Milestone | State | Last gate run | Unlocks claims |
|---|---|---|---|
| M0 kill test | IN PROGRESS | — | C-01, C-02 |

## Plan: M0 Kill Test
Tasks:
1. `pyproject.toml` and Makefile: zero-dep core package, dev extras, `make check` (ruff, mypy --strict, pytest) passing. Done when `make check` passes.
2. `src/hearth/data/providers.toml`: provider facts (Gemini, Anthropic, OpenAI) with prices, cache multipliers, minimums, TTLs, dated and sourced. Done when file loads cleanly and matches provider docs.
3. Invariant tests: `test_named_tests_exist.py`, INV-01 (`test_observe_passthrough_bytes`), INV-09 (`test_no_content_by_default`). Done when tests pass.
4. `src/hearth/` observe mode & trace writer: `hearth.wrap(..., mode="observe")` passthrough proxy + JSONL trace recording. Done when observe passes requests byte-identically and records traces.
5. Pre-registered 20 tasks, mock tools, checkers, and templates (minimal, typical) in `bench/tasks/` & `bench/templates/`. Done when all 20 fixtures and checkers validate.
6. Prototype simulator: per-session token estimation and provider cache rule simulation. Done when trace replay computes read, write, uncached tokens.
7. M0 runner & prototype arms (A Stock, B Best practice, C Hearth safe, D Hearth layout prototype). Done when 4 arms execute 3 runs per task and record metrics.
8. Simulator calibration on hold-out half (MAE target ±10 points). Done when hold-out calibration metric is computed and recorded.
9. Decision memo in STATUS matching §10.1 decision table. Done when memo is written and execution pauses for founder review.

Gate commands:
- `make check`
- `pytest tests/`
- `python -m hearth.bench.runner --m0 --verify`

## Log

(empty)

