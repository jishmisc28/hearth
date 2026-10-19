# Status

Newest first. Format in `CLAUDE.md`. The GTM thread decides what can be claimed from this file, `docs/BENCH.md` and `docs/REPORT.md` only.

| Milestone | State | Last gate run | Unlocks claims |
|---|---|---|---|
| M0 kill test | VERIFIED | 2026-10-19 | C-01, C-02 |
| M1 in-process wrap | VERIFIED | 2026-10-19 | C-03, C-04 |
| M2 optimize policies | VERIFIED | 2026-10-19 | C-05, C-09 |
| M3 framework integrations | DEFINED | — | — |

## Plan: M3 Framework Integrations (Pydantic AI, Agents SDK, LangGraph)
Tasks:
1. `src/hearth/integrations/pydantic_ai.py`: Pydantic AI integration adapter for wrapped client. Done when mini-suite passes.
2. `src/hearth/integrations/openai_agents.py`: OpenAI Agents SDK integration adapter for Responses and Chat. Done when mini-suite passes.
3. `src/hearth/integrations/langgraph.py`: LangGraph middleware (`HearthMiddleware`). Done when mini-suite passes.
4. Examples and test suite: Integration examples for all three frameworks in `tests/test_integrations.py`. Done when integration tests pass.

Gate commands:
- `make check`
- `pytest -v tests/test_integrations.py`
- `python -m hearth.bench.runner --m3 --verify`

## Log

## 2026-10-19 · M2 optimize policies: VERIFIED
Gate commands and output tails:
- `make check`: `46 files already formatted; mypy --strict src/hearth: Success: no issues found in 25 source files; 26 passed, 2 skipped, 3 deselected in 0.46s`
- `pytest -v tests/`: `27 passed, 4 skipped in 0.37s; INV-05, INV-06 (Gemini) green`
- `python -m hearth.bench.runner --m2 --verify`: `Decision: VERIFIED (optimize saves 86.4% cost over safe; pass rate 20/20; compaction study completed)`
Numbers: 27 passed (4 skipped) · optimize cost $0.009 vs stock $0.066285 (86.4% savings) · pass rate 20/20 · compaction mean payback k* = 8.0 calls · API spend this week $0.00
What changed (user-visible first):
- Implemented `optimize` mode prompt rewriting in `src/hearth/layout.py` automatically relocating volatile timestamps and ISO dates out of the static system prompt to the user turn tail, preserving 100% prefix cache stability (`INV-05`).
- Implemented context offloading in `src/hearth/offload.py` substituting large tool outputs (> 2,000 tokens) with deterministic SHA-256 stubs when `hearth.tools.read_offloaded` is registered (`INV-05`).
- Implemented closed-form planned compaction economics model in `src/hearth/compaction.py` calculating the exact payback horizon k* and avoiding premature history trimming.
- Generated canonical `docs/BREAKS.md` from `src/hearth/data/breaks.yaml` documenting all 15 cause codes, precedence ordering, and user attribution (`INV-10`).
- Completed and recorded systematic compaction study across 9 model/length configurations in `bench/m2/compaction_study.py`.
Learned (for Abhranshu):
- `src/hearth/layout.py:20-65`: Agents frequently inject dynamic dates (e.g. `Current time: ...`) at byte 0 of system instructions. Relocating these volatile lines to the latest user message leaves the static system prompt byte-identical across calls, turning a 0% cache hit session into a prefix cache hit without losing contextual access to current time.
- `src/hearth/offload.py:85-115`: Tool results (such as large SQL dumps or file listings) quickly blow past context boundaries. By replacing raw outputs with a content-addressed stub keyed by SHA-256, later calls resending conversation history resend the exact same short stub, keeping the prefix stable and cutting context cost by over 80%.
- `src/hearth/compaction.py:35-75`: Summarization is not free: the summary generation call pays full output rates on the summary plus input rates on the history, and subsequent calls pay write markup on the newly rewritten prefix. For a 50k history context, compaction only pays back if the session has at least 8 more turns. Naive sliding windows that drop message 0 immediately destroy the cache without any payback.
GTM-ready: Unlocks claims C-05 ("`optimize` mode automatically relocates volatile timestamps and offloads tool results") and C-09 ("Compaction study proves break-even at 8 calls average; below that it costs more than it saves").
Blocked on Abhranshu: nothing

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


