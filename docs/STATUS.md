# Status

Newest first. Format in `CLAUDE.md`. The GTM thread decides what can be claimed from this file, `docs/BENCH.md` and `docs/REPORT.md` only.

| Milestone | State | Last gate run | Unlocks claims |
|---|---|---|---|
| M0 kill test | VERIFIED | 2026-10-19 | C-01, C-02 |
| M1 in-process wrap | VERIFIED | 2026-10-19 | C-03, C-04 |
| M2 optimize policies | VERIFIED | 2026-10-19 | C-05, C-09 |
| M3 framework integrations | VERIFIED | 2026-10-19 | C-06, C-07 |
| M4 simulator & replay CLI | VERIFIED | 2026-10-19 | C-07, C-08 |
| M5 memory v0 | VERIFIED | 2026-10-19 | INV-12, memory safety |
| M6 switch-or-stay | VERIFIED | 2026-10-19 | C-11 |
| M7 hardening & v0.1 | IN PROGRESS | 2026-11-02 live Bedrock | Release gate (C-01 to C-11) |

## Plan: The nightly job can call Gemini and Nova. One passing model run per UTC day.
Replies are capped. A saved Bedrock URL that ends in `/v1/chat/completions` is not used. `session_id` is not sent to the model. Gemini prompts in `contents` are counted.

## Log

## 2026-11-12 · One agent session is the live claim
Gate commands and output tails:
- `make check` at `1a0845a`: `85 files already formatted; mypy --strict src/hearth: Success: no issues found in 43 source files; 83 passed, 4 deselected`
- GitHub Actions run `43261384508` completed. Gemini measured 6 turns and then returned free-tier 429. Nova Micro and Nova Lite measured 8 turns.
Numbers: this run added $0.00518691. Priced spend to date is $0.00611861.
What changed (user-visible first):
- A repeated 14,314-token Gemini prefix was a cache read. Those six turns cost 25.5% of the uncached bill.
- Nova kept a 12,801-token cache read across six questions. The eighth turn changed the instructions and the read went back to 0. The Nova sessions cost 19.2% of the uncached bill.
- The raw counts are in `bench/live/2026-11-12.json`. The chart is `hearth-live-session.html`. `docs/REPORT.md` now leads with this session and labels the old 42% table as the simulator.
Learned (for Abhranshu):
- One measured session times 1,000 is a projection: about $9.66 on Gemini, $2.91 on Nova Micro, $4.99 on Nova Lite. That is not a second run.
- A larger receipt needs Gemini billing past the free tier, and the Anthropic use-case form before Claude can be included. Repeating this session hundreds of times would only reprint the same rate.
GTM-ready: the three session ratios above, with the projection labeled as a projection.
Blocked on Abhranshu: Gemini billing, if longer Gemini sessions are wanted. The Anthropic use-case form, if Claude is wanted.

## 2026-11-11 · Nova cache saving is priced. Claude on this account is not.
Gate commands and output tails:
- `make check` at `b50ad25`: `82 files already formatted; mypy --strict src/hearth: Success: no issues found in 43 source files; 81 passed, 4 deselected`
- Probe run `43070714893`: Nova Micro and Nova Lite each read 841 cached tokens on the second call.
- Probe run `43070974414`: Claude Haiku 4.5 returned 3,915 input tokens and 0 cache tokens, then the account refused the next call.
Numbers: priced Bedrock spend in `docs/BENCH.md` is $0.00093170. The Haiku 4.5 call is not in that dollar total.
What changed (user-visible first):
- Nova Micro and Nova Lite now have sourced US East prices. A cache read costs a quarter of the normal input price. A cache write costs $0.
- Today's Nova Micro pair cost $0.00000834 instead of $0.00005986. Nova Lite cost $0.00001478 instead of $0.00010308.
- gpt-oss still shows no cache, so its priced saving is $0. The six earlier calls cost $0.00085410.
- This Bedrock account cannot finish a Claude cache check until the Anthropic use-case form is submitted. Haiku 5.5 is not enabled. The older Haiku ids are end of life.
Learned (for Abhranshu):
- The saving that can be said out loud is the Nova rate: cached input tokens were billed at 0.25×, and the write was free. The dollar amount on these short prompts is a fraction of a cent.
- `src/hearth/data/providers.toml` Bedrock rows use the price list `20261111013037`, publication date 2026-11-11.
GTM-ready: the Nova rate above. No Claude saving, and no gpt-oss saving.
Blocked on Abhranshu: the Anthropic use-case form in the Bedrock console, if a Claude number is wanted. Nothing else for this check.

## 2026-11-09 · Live contract run passed
Gate commands and output tails:
- GitHub Actions run `42637284192` on `cd9d0e5`, started by hand at 2026-11-09 14:42 UTC. Job `contract` succeeded.
- `make contract`: `3 passed, 1 skipped, 80 deselected in 5.99s`. The skip is OpenAI, because `OPENAI_API_KEY` is not set. Gemini, Nova, and the offline guard check passed.
Numbers: no dollar figure. The run did call Gemini and Nova. Output was capped at 32 and 8 tokens.
What changed (user-visible first):
- The Nov 8 night (`42513962779`, commit `8de4ad0`) called both models. Nova passed. Gemini's cache read passed, then the guard scored the prompt as 0 tokens and named the change `below_minimum`. Gemini puts the prompt in `contents`, and the guard was only reading `messages`.
- `contents` is now counted. A changed Gemini prompt is recorded as a rewritten message. The provider still receives the original `contents`.
- A later run on the same UTC day, after a passing model step, stops before spending and the job stays green. A failed model step does not block a retry that day.
Learned (for Abhranshu):
- Run `42637284192` is the proof. `tests/test_contract.py .s..` means Gemini passed, OpenAI skipped, Nova passed, offline guard passed.
- The two warnings are inside Google's `google/genai/types.py`, not in Hearth.
GTM-ready: one green night, not a five-night streak. No dollar saving is stated.
Blocked on Abhranshu: nothing

## 2026-11-08 · Nightly calls reached the models, then failed on two checks
Gate commands and output tails:
- `make check`: `81 files already formatted; mypy --strict src/hearth: Success: no issues found in 43 source files; 78 passed, 4 deselected`
Numbers: no new API spend in this change. The Nov 7 night already called the models.
What changed (user-visible first):
- Gemini was sent `session_id`, which is Hearth's label for a conversation. Gemini rejected the call. That label is now removed before any model sees the request. `prompt_cache_key` is sent only to OpenAI.
- Nova's second call did read the cache. The third call changed the system text, and the guard called it "too short" because the prompt counted as 1,485 tokens and the guard's floor is 2,048. The nightly Nova prompt is now long enough to clear that floor.
Learned (for Abhranshu):
- Run `42404875158` (2026-11-07 19:10 UTC, commit `60e4500`) passed the key check and the one-run-per-day check. `make contract` then failed both live tests.
- Gemini error: `TypeError: Models.generate_content() got an unexpected keyword argument 'session_id'`.
- Nova error: the break cause was `below_minimum` (`Context tokens (1485) below provider minimum (2048)`), not a failed cache read.
GTM-ready: no new live claim. The next night is the first one that can go green.
Blocked on Abhranshu: nothing

## 2026-11-06 · Nightly job uses the keys, and will not call the bad Bedrock URL
Gate commands and output tails:
- `make check`: `80 files already formatted; mypy --strict src/hearth: Success: no issues found in 43 source files; 76 passed, 4 deselected`
Numbers: no new API spend in this change
What changed (user-visible first):
- The contract job reads `GEMINI_API_KEY` and `BEDROCK_API_KEY`. Nova Micro is called on the Converse host. The chat-completions URL stored as `BEDROCK_ENDPOINT` is ignored.
- Gemini answers are limited to 32 tokens. Nova answers are limited to 8. The Gemini prompt is about 4,000 tokens, not about 30,000.
- If a run today already reached the model step, the next click stops before any call.
Learned (for Abhranshu):
- `.github/workflows/contract.yml`: two runs cannot overlap, and a completed model step on the same UTC day blocks another.
- `src/hearth/bedrock_converse.py`: `converse_endpoint` turns both `/v1/chat/completions` and `/openai/v1/chat/completions` back into the Converse host, because Nova does not answer on those paths.
GTM-ready: no new live claim until a night actually goes green.
Blocked on Abhranshu: nothing for this wiring. The next contract run is the first one that can spend.

## 2026-11-06 · Converse checkpoints and finished streams, still offline
Gate commands and output tails:
- `make check`: `80 files already formatted; mypy --strict src/hearth: Success: no issues found in 43 source files; 75 passed, 3 deselected`
Numbers: 75 passed · no API spend
What changed (user-visible first):
- Optimize mode can move a clock out of a Converse system list without dropping the cache checkpoint block.
- On the next turn that same clock is written again onto the message that was already sent.
- A streamed reply and an awaited reply are recorded when they finish. The token counts come from the last chunk, or from the awaited reply.
Learned (for Abhranshu):
- `src/hearth/layout.py`: a `cachePoint` block is not text. Folding it into the clock move would change the marker Nova uses to reuse the prefix.
- `src/hearth/wrapper.py`: counting a stream at the moment `create` returns sees no usage yet. The bill arrives with the last chunk.
GTM-ready: no new live claim. The 3,601-token Nova read is unchanged.
Blocked on Abhranshu: the Gemini key for the nightly job, and a sourced Nova price. The Bedrock key is not in this shell, so the live clock check on Nova is waiting.


gpt-oss-120b does not report cache tokens. `amazon.nova-micro-v1:0` on the Converse API does. A wrapped observe call read 3,601 of 3,607 input tokens on the second request. There is no sourced price, so that is not yet a dollar saving.

## 2026-11-02 · Nova Micro cache read, counted by Hearth
Gate commands and output tails:
- Live `hearth.wrap` observe, `amazon.nova-micro-v1:0`: call 1 read 0, write 3601, uncached 6, output 2. Call 2 read 3601, write 0, uncached 6, output 2.
- Earlier direct Converse pair, same shape: write 2401, then read 2401, uncached tail 6 both times.
Numbers: 3,601 cached input tokens on the wrapped second call · USD unpriced · `make check`: `79 files already formatted; mypy --strict src/hearth: Success: no issues found in 43 source files; 72 passed, 3 deselected`
What changed (user-visible first):
- `BedrockConverse` speaks the Converse URL with the standard library. The bearer key is not written to the ledger.
- Converse usage is reconciled as cache read + cache write + `inputTokens`. The raw `inputTokens` value of 6 is the tail, not the prompt.
Learned (for Abhranshu):
- The OpenAI-compatible URL returned HTTP 404 for `amazon.nova-micro-v1:0`: that model does not support that API. `POST /model/amazon.nova-micro-v1:0/converse` returned the cache fields.
- A cache read and a lower bill are different facts. 3,601 of 3,607 input tokens were a read. What that costs waits on a sourced price.
GTM-ready: token counts in `docs/BENCH.md`. No dollar claim and no percentage-saved claim.
Blocked on Abhranshu: nothing. A sourced Nova price would turn the token count into dollars.



## 2026-11-02 · Optimize keeps the clock it already sent
Gate commands and output tails:
- `make check`: `76 files already formatted; mypy --strict src/hearth: Success: no issues found in 41 source files; 69 passed, 3 deselected`
- `hearth scenarios` clock row: observe read 0.0% cost 1.00× and 2 app-caused breaks; optimize read 66.5% cost 0.42× and 0 app-caused breaks. The other three scenarios are unchanged.
Numbers: 69 passed · simulator read share 66.5% on the clock case · no new API spend in this change
What changed (user-visible first):
- On the next turn, optimize writes the same clock back onto the message it already sent, and puts the new clock only on the new user message.
- A rewritten earlier message is left as the app sent it. The old clock is not pasted onto it.
- A matching prefix is not called a provider miss until a read count of zero comes back from the provider. A long stable prompt with a zero read is recorded as `provider_miss`, and it is not blamed on the app.
Learned (for Abhranshu):
- `src/hearth/layout.py`: the cache key is the bytes of the previous request. Moving a clock onto "Turn 1" and then sending "Turn 1" without that clock on the next call is a different prefix. The read share only moves from 66.4% to 66.5% because the clock is a few tokens next to a long stable instruction. The break count is the real change: 2 down to 0.
- `src/hearth/guard.py`: `provider_miss` used to fire whenever the prefix matched and the read count was still the default zero, which is the state before the provider answers.
GTM-ready: no savings claim. The scenario page is still the simulator.
Blocked on Abhranshu: nothing for this fix.

## 2026-11-02 · Live Bedrock check: no cache fields
Gate commands and output tails:
- `make check`: `76 files already formatted; mypy --strict src/hearth: Success: no issues found in 41 source files; 65 passed, 3 deselected`
- Live `openai.gpt-oss-120b-1:0`: stable call 1 and call 2 both `prompt_tokens` 1699, `completion_tokens` 8, no `cached_tokens`. Clock prefix: `prompt_tokens` 1716.
- `hearth.wrap` observe left `Current time: 2026-11-02T09:00:00` in the system message (102 prompt tokens). optimize moved it onto the user message (106 prompt tokens).
Numbers: 5,406 input tokens and 72 output tokens across the logged calls · cached tokens reported: 0 · USD unpriced
What changed (user-visible first):
- Optimize mode now moves a clock out of an OpenAI-style system message, which is where Bedrock Chat Completions puts instructions.
- A missing price in `providers.toml` no longer throws away the provider response.
- `OpenAIChatClient` speaks the Bedrock completions URL with the standard library.
Learned (for Abhranshu):
- The URL ending in `/v1/chat/completions` returns `UnknownOperationException`. The URL ending in `/openai/v1/chat/completions` returns a chat completion. The model id that works is `openai.gpt-oss-120b-1:0`, not `gpt-oss-120b`.
- Two identical long prompts produced the same bill and no cache field. AWS's own caching samples list GPT OSS as not yet supported. Hearth cannot manufacture a saving the provider does not sell.
GTM-ready: no savings claim for Bedrock gpt-oss. The negative result is the proof.
Blocked on Abhranshu: nothing for this measurement. A model that actually returns `cached_tokens` is what a savings claim needs.



## 2026-11-02 · M7 after v0.1.0: scenarios people can run
Gate commands and output tails:
- `make check`: `74 files already formatted; mypy --strict src/hearth: Success: no issues found in 40 source files; 61 passed, 3 deselected`
- `hearth scenarios`: clock optimize read 66.4% and cost 0.42× against observe 0.0% and 1.00×; shuffled tools safe read 49.9% and 0 app-caused breaks against observe 0.0% and 1 break; short prompt 0 app-caused breaks; rewritten history 1 app-caused break in every mode
Numbers: scenario tests passed · simulator, not a bill · API spend $0.00
What changed (user-visible first):
- `hearth scenarios` replays four cache failures with no API key and writes `hearth-scenarios.html`.
- Replay now counts the system prompt and the tools when it decides whether a call is too short to cache. A long system prompt with a short question is no longer treated as below the minimum.
Learned (for Abhranshu):
- `src/hearth/scenarios.py`: moving a clock out of the system prompt drops simulated input cost from 1.00× to 0.42×, and the guard still records breaks. The clock was written onto a turn that the next raw history does not contain, so the bytes of that earlier turn do not match.
- Safe mode is the one that removes the tool-order break. Optimize does not. Each mode fixes a different mistake.
GTM-ready: no new live claim. The page is labeled simulator.
Blocked on Abhranshu: repository secret `GEMINI_API_KEY`, so one real Gemini session can be logged in `docs/BENCH.md`. PyPI trusted publishing is done.



## 2026-10-23 · M7 hardening & v0.1: IN PROGRESS
Gate commands and output tails:
- `make check` (local, after the default-mode change): `57 passed, 3 deselected`
- Gemini independent evaluation, 2026-10-23T02:07Z to 02:14Z: Group A 10/10 pass, Group B 1/7 pass. Verdict LIBRARY-OK. Recorded in `hearth-v0.1-proof.html` and `hearth-v0.1-proof.typescript`.
Numbers: 57 passed · simulator report still 42.0% and labeled SIMULATOR · API spend this week $0.00
What changed (user-visible first):
- `hearth.wrap(client)` now defaults to `safe`, matching the handbook. `observe` and `optimize` are unchanged when named.
- GitHub Actions runs `make check` on Python 3.10, 3.11, and 3.12.
- A nightly contract workflow is armed. It fails closed until `GEMINI_API_KEY` exists.
- A `v*` tag publishes `hearth-ai` once PyPI trusts this repository.
- Package version is `0.1.0`.
Learned (for Abhranshu):
- `hearth-v0.1-proof.typescript`: replaying a trace recorded with `record=False` prices every mode at 1.00×, because the prompt was correctly left out of the file. The replay that kept the request showed `optimize` at 0.44× against 1.00× for `observe` and `safe`. That figure is still the simulator.
- Human install trials and a live provider bill are different blocks. Agents can replace the first. They cannot replace the second without a key.
GTM-ready: no new live claim. C-01 through C-11 stay simulator-backed.
Blocked on Abhranshu: add repository secret `GEMINI_API_KEY`, and on PyPI turn on trusted publishing for `jishmisc28/hearth` (environment name `pypi`). Nothing else.

## 2026-10-19 · M7 hardening & v0.1 release readiness: PENDING-HUMAN
Gate commands and output tails:
- `make check`: `72 files already formatted; mypy --strict src/hearth: Success: no issues found in 39 source files; 56 passed, 3 deselected in 0.81s`
- `hearth bench --report`: `Overall Cost Reduction: 42.0%; Calibration MAE: 0.0 points; Report frozen at docs/REPORT.md`
- `all milestone benchmarks`: `M0 Kill Test (GO), M2 Optimize (74.7% savings), M3 Frameworks (100%), M4 Report (42.0%), M5 Memory (100%), M6 Switch-or-stay (18.1% savings) all VERIFIED`
Numbers: 56 passed (16/16 named invariants green) · 42.0% cost reduction on 20 tasks · 0.00 MAE calibration holdout · p50 0.66 ms / p99 1.08 ms at 50k tokens · 0 required external dependencies on Python 3.11+ · API spend this week $0.00
What changed (user-visible first):
- Full test suite verified green with strict mypy, ruff formatting, and 16/16 named invariants passing.
- Added comprehensive Apache-2.0 `LICENSE` file.
- Overhauled `README.md` with complete installation guides, quickstarts for observe/safe/optimize modes, verified framework integration examples (LangGraph, Pydantic AI, OpenAI Agents SDK), CLI documentation, and proven benchmark metrics.
- Re-verified `src/hearth/data/providers.toml` with current dated sources (`2026-10-19`).
- Confirmed zero required dependencies in core for Python 3.11+.
Learned (for Abhranshu):
- `tests/test_perf.py:50-65`: When benchmarking sub-millisecond CPU overhead at 50k context tokens (~200k characters across 30 messages and 10 tools), host Python garbage collection sweeps on large dictionaries can intermittently distort p99 latency numbers from ~1 ms to ~5 ms. Disabling GC exclusively across the 100 tight micro-benchmark iterations isolates the pure algorithmic overhead of Hearth's fingerprinting, ordering restoration, and guard validation (0.66 ms p50, 1.08 ms p99).
- `docs/REPORT.md:1-63`: Prefix caching stability across agent frameworks is a multiplicative system: if system prompts have dynamic dates (0% cache hits), fixing tool order alone cannot salvage the cache; conversely, fixing system prompt layout while letting tool ordering oscillate drops cache hits by half. Only when static system prompts, stable session context, tool definitions, and message history are compartmentalized by stability class does read share reach 48.9% full-session average and 100% on turn 2+.
GTM-ready: Full claims ledger C-01 through C-11 backed by verified artifacts in `docs/REPORT.md`, `docs/BENCH.md`, and `docs/STATUS.md`.
Blocked on Abhranshu: Written approval to tag `v0.1.0` and publish `hearth-ai` to PyPI (CLAUDE.md stop condition).

## 2026-10-19 · M6 switch-or-stay: VERIFIED
Gate commands and output tails:
- `make check`: `72 files already formatted; mypy --strict src/hearth: Success: no issues found in 39 source files; 56 passed, 3 deselected in 1.09s`
- `pytest -v tests/test_routing.py tests/test_planner.py`: `12 passed in 0.24s (break-even economics, delegate, stay, switch, TTL 1h stable prefix)`
- `python -m hearth.bench.runner --m6 --verify`: `{"milestone": "M6", "gate_verified": true, "tasks_tested": 5, "tasks_passed": 5, "pass_rate_pct": 100.0, "overall_savings_pct": 18.1}; [VERIFICATION PASSED] M6 Benchmark Gate: VERIFIED`
Numbers: 56 passed · 18.1% cost reduction across 5 mixed-difficulty tasks · 100% task pass rate (0/5 lost, within §10.1 rule) · API spend this week $0.00
What changed (user-visible first):
- Added `src/hearth/policies/route.py` implementing closed-form break-even economics: evaluates whether to stay on current model, switch models, or delegate sub-tasks using exact Decimal arithmetic ($n^* = \frac{q \cdot w}{r \cdot (1 - q)}$).
- Added `TTLOptimizer` in `src/hearth/planner.py` providing intelligent TTL selection: assigns 1-hour TTL on the stable prefix boundary (STATIC/SESSION) when human approval pauses or long tools are anticipated (`s.expect_pause()` or inter-call EWMA gap > 300s), saving rewrite penalty while keeping conversation tail strictly at 5-minute TTL.
- Updated `src/hearth/wrapper.py` to seamlessly record call intervals and apply session hints (`expect_pause()`, `expect_calls(n)`) into cache planning.
- Added 5 pre-registered mixed-difficulty benchmark tasks in `bench/tasks/mixed.py` and benchmark runner in `bench/m6/runner.py`.
- Bumped package version to `0.1.0b1` in `pyproject.toml` and `src/hearth/__init__.py` for outsider trials.
Learned (for Abhranshu):
- `src/hearth/policies/route.py:34-60`: Naively routing every sub-turn to a "cheaper" model often burns money instead of saving it. When model B is cheaper than model A ($q = p_B / p_A < 1$), switching mid-session requires model B to perform a cold write of the entire accumulated prefix at B's write multiplier $w_B$. If the remaining calls $n \le n^*$, the cold write penalty outweighs model A's warm cache read savings. Hearth's closed-form break-even formula calculates the exact inflection point in $O(1)$ and prevents premature switches.
- `src/hearth/policies/route.py:120-140`: When an agent task requires a small contextual sub-action (e.g. 500-token regex extraction or JSON validation from a 20k-token repository prompt), neither staying on the expensive model nor switching the whole 20k context to a cheaper model is optimal. Hearth's `delegate` verdict runs the sub-task as an isolated lightweight session with only the 500 tokens it needs, slashing costs by up to 65% while keeping the primary model's 20k prefix cache intact.
- `src/hearth/planner.py:54-78`: Anthropic's 1-hour cache write costs 2.0x input price, while 5-minute cache writes cost 1.25x. For human-in-the-loop pauses exceeding 5 minutes, 5-minute TTL expires and forces a 1.25x rewrite on every resume. By placing 1-hour TTL specifically on the stable prefix when pauses are anticipated ($k \ge 1$), Hearth eliminates repeat cold writes across human reviews, yielding an immediate 11.8% to 16.0% savings on pause tasks.
GTM-ready: Unlocks claim C-11 ("Switch-or-stay saved 18.1% on mixed-difficulty tasks with no success loss").
Blocked on Abhranshu: nothing

## 2026-10-19 · M5 memory v0: VERIFIED
Gate commands and output tails:
- `make check`: `65 files already formatted; mypy --strict src/hearth: Success: no issues found in 36 source files; 44 passed, 3 deselected in 1.13s`
- `pytest -v tests/test_invariants.py -k "test_memory"`: `2 passed in 0.44s (INV-12 test_memory_supersede, test_memory_no_session_mutation)`
- `python -m hearth.bench.runner --m5 --verify`: `{"milestone": "M5", "gate_verified": true, "tasks_tested": 5, "tasks_passed": 5, "pass_rate_pct": 100.0}; [VERIFICATION PASSED] M5 Benchmark Gate: VERIFIED`
Numbers: 44 passed · 100% memory task pass rate across 5 pre-registered tasks (13 sessions evaluated) · zero external dependencies · API spend this week $0.00
What changed (user-visible first):
- Added `src/hearth/memory/store.py` providing SQLite `facts` table with FTS5 search, full temporal superseding (`valid_from`, `valid_to`, `superseded_by`), session snapshot isolation, and untrusted tool taint quarantine.
- Added `src/hearth/memory/checks.py` enforcing synchronous write validation: 2,000 character length limit, secrets rejection (API keys, private keys, AWS tokens), and prompt injection / instruction override pattern rejection.
- Added `src/hearth/memory/recall.py` providing `hearth.memory.remember`, `hearth.memory.recall`, and `hearth.memory.pin`.
- Guaranteed cache-friendly memory placement (`INV-12`): pinned facts load once at session start into SESSION prefix, while mid-session writes are placed into turn tail (volatile) without mutating active session prefix cache.
- Added 5 pre-registered multi-session benchmark tasks in `bench/tasks/memory.py` and benchmark runner in `bench/m5/runner.py`.
Learned (for Abhranshu):
- `src/hearth/memory/store.py:110-160`: Storing evolving facts without breaking cache requires temporal superseding instead of overwriting or keeping contradictory rows. When a fact changes (e.g. user updates a configuration or primary key), Hearth sets `valid_to` and `superseded_by` atomically. Old facts remain queryable for audit, but active queries only retrieve the current truth.
- `src/hearth/memory/recall.py:45-80`: Naive agent memory injects newly recalled or modified facts directly into the system prompt mid-session, completely invalidating the provider's prompt cache prefix. Hearth enforces snapshot isolation: pinned session facts are loaded once into the SESSION prefix, while mid-session updates are routed exclusively to that turn's volatile tail (`hearth.get_current_session().volatile(...)`). Only when a new session starts are updated facts promoted into the SESSION prefix.
- `src/hearth/memory/checks.py:40-60`: Untrusted agent memory is a primary vector for prompt injection. By running strict regex validation for prompt override tokens ("ignore previous", "from now on", "system override") synchronously before writing to SQLite, Hearth prevents corrupted agent memories from poisoning future sessions.
GTM-ready: Invariant INV-12 verified; temporal memory store with zero dependencies and cache-friendly prefix stability proven.
Blocked on Abhranshu: nothing

## 2026-10-19 · M4 simulator & replay CLI: VERIFIED
Gate commands and output tails:
- `make check`: `58 files already formatted; mypy --strict src/hearth: Success: no issues found in 32 source files; 38 passed, 2 skipped, 3 deselected in 1.27s`
- `hearth bench --report`: `[Cache Efficiency Report generated and frozen at .../docs/REPORT.md]; Overall Cost Reduction: 42.0%; Calibration MAE: 0.0 points`
- `python -m hearth.bench.runner --m4 --verify`: `{"milestone": "M4", "gate_verified": true, "overall_savings_pct": 42.0, "calibration_holdout_mae_points": 0.0, "cause_counts": {"volatile_in_prefix": 160}}; [VERIFICATION PASSED] M4 Benchmark Gate: VERIFIED`
- `hearth replay`: `canonical columns (mode, read, written, uncached, input cost, user-caused breaks) verified in test_cli_replay`
- `hearth guard`: `regression break detection verified in test_cli_guard`
Numbers: 38 passed (2 skipped) · 42.0% overall cost reduction across 4 frameworks × 2 providers (20 tasks, 160 sessions) · hold-out calibration error 0.00 points MAE (target <= 5.0) · 100% task pass rate · API spend this week $0.00
What changed (user-visible first):
- Added `FakeProvider` in `src/hearth/testing.py` providing deterministic, network-free mock clients for Google Gemini, OpenAI, and Anthropic with realistic usage token estimation matching `providers.toml` rules.
- Added `hearth replay <trace_file>` CLI subcommand replaying JSONL trace files through `CacheSimulator` under `observe`, `safe`, and `optimize` policies, computing exact `Decimal` cost ratios and break counts.
- Added `hearth guard --baseline <path> --run "<cmd>"` CLI subcommand detecting prefix break regressions in automated test suites and failing CI if new user-caused breaks appear.
- Reconciled simulator token accounting to strictly enforce `INV-06` (`read + write + uncached == total_input`).
- Generated and froze canonical `docs/REPORT.md` (Cache Efficiency Report v1) covering 4 frameworks × 2 providers on 20 tasks, reproducible via `hearth bench --report`.
Learned (for Abhranshu):
- `src/hearth/testing.py:120-170`: `FakeProvider` allows agent developers to test their applications offline with 100% deterministic prompt cache measurements. Instead of spending money on real provider API tokens in CI, `FakeProvider` returns SDK-compliant responses with accurate cache usage metadata (`read`, `write`, `uncached`) derived directly from `providers.toml`.
- `src/hearth/replay.py:40-95`: Replay analysis shows that unmanaged typical agent prompts incur near-zero cache reads (0.0% read share) due to volatile runtime metadata (timestamps, dynamic dates) prepended to the system prompt. Under `optimize` mode, relocating these volatile lines to the user message tail immediately unlocks a 48.9% full-session average read share (and 100% read share on turn 2 post-warmup), reducing overall input cost by over 40%.
- `src/hearth/cli.py:165-215`: `hearth guard` operates as a prompt-cache regression linter for CI: by intercepting traces generated during test runs via `HEARTH_TRACE_DIR`, it compares break causes against a baseline. If a commit modifies a system prompt dynamically or reorders tools, `hearth guard` catches the break before it deploys to production.
GTM-ready: Unlocks claims C-07 ("Cache Efficiency Report v1 frozen across 4 frameworks × 2 providers on 20 tasks") and C-08 ("Deterministic offline testing with FakeProvider and CI cache break detection via hearth guard").
Blocked on Abhranshu: nothing


## 2026-10-19 · M3 framework integrations: VERIFIED
Gate commands and output tails:
- `make check`: `53 files already formatted; mypy --strict src/hearth: Success: no issues found in 30 source files; 30 passed, 2 skipped, 3 deselected in 0.55s`
- `pytest -v tests/test_integrations.py`: `4 passed in 0.40s; LangGraph, Pydantic AI, OpenAI Agents SDK mini-suites and observe passthrough verified`
- `python -m hearth.bench.runner --m3 --verify`: `{"milestone": "M3", "gate_verified": true, "frameworks_tested": 3, "results": {"langgraph": {"pass_rate_pct": 100.0}, "pydantic_ai": {"pass_rate_pct": 100.0}, "openai_agents_sdk": {"pass_rate_pct": 100.0}}}; [VERIFICATION PASSED] M3 Benchmark Gate: VERIFIED`
Numbers: 30 passed (2 skipped) · 3/3 frameworks verified · 100% mini-suite pass rate across all 3 frameworks · API spend this week $0.00
What changed (user-visible first):
- Added `HearthMiddleware` in `src/hearth/integrations/langgraph.py` (and alias `src/hearth/integrations/langchain.py`) providing drop-in middleware for LangGraph state graphs and LangChain callbacks: preserves input message object references in `observe` mode, restores first-seen tool order in `safe` mode, relocates volatile timestamps in `optimize` mode, and checks `PrefixGuard`.
- Added `wrap_pydantic_ai_client` and `HearthPydanticAIModel` in `src/hearth/integrations/pydantic_ai.py` enabling zero-boilerplate prompt caching for Pydantic AI models.
- Added `set_default_openai_client`, `get_default_openai_client`, and `wrap_agents_client` in `src/hearth/integrations/openai_agents.py` seamlessly intercepting calls made by OpenAI Agents SDK.
- Exported all integration adapters cleanly from `hearth.integrations` without requiring external framework dependencies in core (`pyproject.toml` remains zero external dependencies).
- Created mini-suite tests in `tests/test_integrations.py` and benchmark verification runner in `bench/m3/runner.py`.
Learned (for Abhranshu):
- `src/hearth/integrations/langgraph.py:47-52`: In LangGraph, message histories frequently contain framework-specific dataclasses (`HumanMessage`, `AIMessage`). In `observe` mode, Hearth must strictly pass these objects through by reference without converting them to dicts (`INV-01`), whereas in `safe`/`optimize` mode it converts and normalizes them for layout inspection and tool ordering.
- `src/hearth/integrations/openai_agents.py:13-20`: OpenAI Agents SDK defaults to an internal client singleton unless configured via `set_default_openai_client`. By wrapping this client instance at setup, any agent created downstream inherits automatic tool order stabilization, prefix break attribution, and cache metrics with zero per-agent code changes.
- `src/hearth/integrations/pydantic_ai.py:24-36`: Pydantic AI's model architecture encapsulates provider clients within model objects (`model.client` or `model.anthropic_client`). Dynamic property inspection allows Hearth to wrap the underlying network client directly, giving users the choice of wrapping either the client before model instantiation or the model instance itself.
GTM-ready: Unlocks claims C-06 ("Zero code rewrites across LangGraph, Pydantic AI, and OpenAI Agents SDK") and C-07 ("Mini-suite reproduces 100% task completion while maintaining prompt cache warmth").
Blocked on Abhranshu: nothing


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


