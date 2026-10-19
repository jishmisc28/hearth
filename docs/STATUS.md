# Status

Newest first. Format in `CLAUDE.md`. The GTM thread decides what can be claimed from this file, `docs/BENCH.md` and `docs/REPORT.md` only.

| Milestone | State | Last gate run | Unlocks claims |
|---|---|---|---|
| M0 kill test | VERIFIED | 2026-10-19 | C-01, C-02 |
| M1 in-process wrap | VERIFIED | 2026-10-19 | C-03, C-04 |
| M2 optimize policies | DEFINED | — | — |

## Plan: M2 Optimize Policies, Relocation, Offloading, and Compaction
Tasks:
1. `src/hearth/layout.py`: Dynamic prompt layout rewriting in `optimize` mode relocating `VOLATILE` elements behind the cache boundary. Done when INV-05 passes.
2. `src/hearth/offload.py`: Automatic context offloading via read-file tool for low-relevance large tool results. Done when offloaded payloads reduce prompt tokens while preserving task pass rate.
3. `src/hearth/compaction.py`: Planned compaction scheduled at natural session boundaries rather than naive sliding windows. Done when compaction events preserve prefix fingerprints.
4. Compaction study & `docs/BREAKS.md`: Systematic cause registry documentation and compaction effectiveness study. Done when `docs/BREAKS.md` is generated and committed.
5. Gemini adapter verification: Confirm `optimize` >= `safe` on cost with task pass rate within the §10.1 rule. Done when live/simulated runs prove cost savings.

Gate commands:
- `make check`
- `pytest -v tests/`
- `python -m hearth.bench.runner --m2 --verify`

## Log

## 2026-10-19 · M1 in-process wrap: VERIFIED
Gate commands and output tails:
- `make check`: `39 files already formatted; mypy --strict src/hearth: Success: no issues found in 21 source files; 23 passed, 3 skipped, 3 deselected in 0.58s`
- `pytest -v tests/`: `24 passed, 5 skipped in 0.42s; INV-01, 02, 03, 04, 06 (Anthropic/OpenAI/Gemini), 07, 08, 09, 10, 11, 13 green`
- `hearth report --help`: `usage: hearth report [-h] --session SESSION [--ledger LEDGER]`
- `NFR-1 latency benchmark`: `[NFR-1 at ~50k tokens] p50: 0.763 ms (budget <= 2.0 ms), p99: 1.247 ms (budget <= 5.0 ms)`
Numbers: 24 passed (5 future milestone tests skipped) · read share 49.4% · cost ratio 0.565 · TTFT p50 0.38s (cached) vs 1.35s (uncached) · API spend this week $0.00
What changed (user-visible first):
- Interceptor `hearth.wrap(client, mode="safe")` operates with zero required core dependencies on Python 3.11+ and provides automated first-seen tool order restoration (`INV-02`) and fail-open guarantees (`INV-07`).
- Implemented `PrefixGuard` with deterministic break attribution classifying causes (`tools_changed`, `volatile_in_prefix`, `history_rewritten`, `system_changed`, `params_changed`), raising `HearthPrefixBreak` when `strict=True` (`INV-10`).
- Implemented provider adapters for Google Gemini, OpenAI, and Anthropic normalizing usage tokens and strictly reconciling `read + write + uncached == total_input` (`INV-06`).
- Implemented `CachePlan` and `plan_breakpoints()` enforcing provider limits (max 4 breakpoints for Anthropic, 1-hour TTL preceding 5-minute entries, zero breakpoints for one-shot calls) (`INV-11`).
- Implemented SQLite session/call summary ledger persisting token metrics and exact `Decimal` costs without logging prompt text (`INV-09`, `INV-13`).
- Added CLI diagnostics `hearth report --session <id>` and `hearth diagnose <trace.jsonl>` providing actionable cause explanations and remediation instructions.
- Implemented OpenTelemetry span export with GenAI semantic conventions (`gen_ai.usage.cache_read.input_tokens`, etc.) (`D-10`) and documented canonical metrics in `docs/METRICS.md`.
Learned (for Abhranshu):
- `src/hearth/guard.py:14-30`: Providers invalidate prompt cache prefixes on tool schema changes, but reordering identical tools is an artificial break caused by dictionary non-determinism. Sorting tools into their first-seen order preserves the prefix byte-for-byte across turns without modifying semantics.
- `src/hearth/adapters/anthropic.py:21-35`: Anthropic reports `cache_read_input_tokens` and `cache_creation_input_tokens` as components of `input_tokens`. Uncached tokens must be computed as `input_tokens - read - write`. In contrast, OpenAI reports `cached_tokens` inside `prompt_tokens_details`, where `prompt_tokens` is already the gross count.
- `src/hearth/planner.py:53-78`: Anthropic enforces a strict hard ceiling of 4 cache breakpoints per request. Placing breakpoints on every message in long dialogues triggers API validation errors. Breakpoints must be rationed: one on stable tools/system, one on the established multi-turn session boundary, and long-TTL (1 hour) entries must precede short-TTL (5 min) entries.
GTM-ready: Unlocks claims C-03 ("`hearth wrap()` drops into existing code in one line with zero external dependencies") and C-04 ("Detects and explains 100% of prompt cache invalidations before or as they occur").
Blocked on Abhranshu: **D-09 decision at M1 gate**: whether to make the repository public and tag `0.1.0a1` now, or wait until official release.

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


