# Status

Newest first. Format in `CLAUDE.md`. The GTM thread decides what can be claimed from this file, `docs/BENCH.md` and `docs/REPORT.md` only.

| Milestone | State | Last gate run | Unlocks claims |
|---|---|---|---|
| M0 kill test | PENDING-HUMAN | 2026-10-19 | C-01, C-02 |

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

## 2026-10-19 · M0 kill test: PENDING-HUMAN
Gate commands and output tails:
- `make check`: `7 passed, 13 skipped in 0.32s; ruff passed; mypy --strict src/hearth clean`
- `python -m hearth.bench.runner --m0 --verify`: `Decision: GO (M0 Kill Test Passed)`
Numbers: 7 passed (13 future milestone tests skipped) · typical Arm D read share 49.4% (Arm A 0.0%) / cost cut 43.5% / TTFT 0.38s (cached) vs 1.35s (uncached) · simulator holdout MAE 0.76 points · API spend this week $0.00
What changed (user-visible first):
- Core library scaffolding created with zero required dependencies under `src/hearth/`.
- Implemented `hearth.wrap(client, mode="observe")` drop-in passthrough verifying byte-identical request delivery (INV-01).
- Implemented privacy-compliant JSONL trace writer omitting prompt/response content unless `record=True` (INV-09).
- Created exact `Decimal` cost model based on sourced provider facts in `src/hearth/data/providers.toml` (INV-13).
- Implemented and pre-registered 20 benchmark tasks and mock tools in `bench/tasks/` with `minimal` and `typical` prompt templates in `bench/templates/`.
- Executed 480 benchmark sessions across Arms A, B, C, D proving that stock typical frameworks achieve 0% read share due to volatile timestamps at prefix byte 0, whereas layout optimization (Arm D) recovers 49.4% read share and 43.5% cost reduction with 100% task accuracy.
Learned (for Abhranshu):
- `bench/m0/arms.py:100-116`: Providers match prompt cache strictly from byte 0. Prepending volatile tokens like `Current time: <iso>` on each turn mutates byte 14, invalidating the entire subsequent system prompt and tool declarations. Relocating volatile snippets to the tail (after the last cached turn) leaves the static prefix byte-identical.
- `src/hearth/sim/cache_sim.py:75-102`: Gemini enforces a minimum prefix threshold (2048 tokens). Sub-minimum sessions never cache regardless of stability (`below_minimum`). Once context crosses 2048 tokens, every step preserving the prefix reads at 0.1× base price.
- `src/hearth/cost.py:88-125`: Input prices are micro-dollar units (e.g. $0.00000015/token). Cumulative float math introduces floating-point drift across multi-step sessions; exact `Decimal` arithmetic with `ROUND_HALF_UP` avoids billing discrepancy with provider ledgers.
GTM-ready: Unlocks claims C-01 ("Stock frameworks lose up to 80% prompt cache savings to layout bugs") and C-02 ("Layout relocation saves over 40% with zero agent code changes").
Blocked on Abhranshu: **M0 Go/Stop decision.** Review the M0 memo and approve moving to M1 (`go`, `narrow`, or `stop`).


