# Cache Efficiency Report v1

The live numbers are in the next section. The 42% figure further down is the offline simulator. It is not a provider bill.

## Live agent session · 2026-11-12

Run `43261384508`, commit `1a0845a`. Raw counts: `bench/live/2026-11-12.json`. Chart: `hearth-live-session.html`.

The same instructions, about 12,000 to 14,000 tokens, were sent with a new short question on each turn. Replies were capped at 16 tokens. Dollars use the sourced prices in `providers.toml`.

| Model | Turns measured | Cache read on the second turn | Session cost | Uncached cost of those tokens | Session cost as a share of uncached | 1,000 sessions, projected saving |
|---|---:|---:|---:|---:|---:|---:|
| Gemini 2.5 Flash | 6, then the free-tier quota stopped the run | 14,314 of 14,410 (99.3%) | $0.00330885 | $0.01297080 | 25.5% | $9.66 |
| Nova Micro | 8, including the changed instruction | 12,801 of 12,807 (99.95%) | $0.00069191 | $0.00360430 | 19.2% | $2.91 |
| Nova Lite | 8, including the changed instruction | 12,801 of 12,807 (99.95%) | $0.00118615 | $0.00617874 | 19.2% | $4.99 |

On Nova, the eighth turn changed the instructions. The cache read went back to 0 and a new cache write was recorded. Gemini did not reach that turn: the key returned HTTP 429 on the free-tier request quota.

The 1,000-session column multiplies this measured session by 1,000. It is not a second experiment.

gpt-oss is omitted because the earlier calls returned no cache fields. Claude is omitted because this Bedrock account blocked Haiku until the Anthropic use-case form is submitted.

## Live tool session · 2026-11-12

Run `43264643293`, commit `c99adae`. Raw counts: `bench/live/2026-11-12-tools.json`.

The instructions and the cache checkpoint stayed fixed. Three tools were sent on every turn. Five questions each produced a tool call, and each finished tool call was followed by a short tool result, so the conversation grew. The sixth turn changed one tool description. Replies were allowed 512 tokens. Every turn stopped on `tool_use`.

The first turn did not write the cache. It read 13,266 tokens that run `43264299216` had written about two minutes earlier. That earlier attempt then failed on the next turn. Two failed attempts cost $0.00078748 and are in `docs/BENCH.md`. They are not in the table below.

| Model | Turns measured | Cache read on the second turn | Cache read after the tool change | Session cost | Uncached cost of those tokens | Session cost as a share of uncached | 1,000 sessions, projected saving |
|---|---:|---:|---:|---:|---:|---:|---:|
| Nova Micro | 6 | 13,278 of 13,386 (99.2%) | 13,336 of 13,884 (96.1%) | $0.00082708 | $0.00292160 | 28.3% | $2.09 |
| Nova Lite | 6 | 13,272 of 13,363 (99.3%) | 13,300 of 13,776 (96.5%) | $0.00137503 | $0.00496152 | 27.7% | $3.59 |

Changing the tool description did not clear the cache read. The checkpoint is on the instructions, and the tools sit outside it. The uncached tail grew because the conversation and the tool calls were appended. The read stayed on the instructions and grew by a few dozen tokens.

The 1,000-session column multiplies this measured session by 1,000. It is not a second experiment. Gemini was not called. The free-tier quota had already stopped the question session.


---

**Simulator, frozen 2026-10-19.** The table below repeats the same result on every framework row. It is a rehearsal, not the live bill above.

## Executive Summary

Stock agent implementations systematically defeat prompt caching across all major frameworks. Dynamic runtime context (timestamps, request IDs) placed in the static prefix combined with unmanaged tool order produces near-zero cache read shares under default configurations.

Applying **Hearth Optimize** relocates volatile elements out of the prefix, stabilizes tool definitions, and enforces content-addressed offloading without altering model behavior.

- **Overall Cost Reduction:** **42.0%** across all evaluated frameworks and providers.
- **Cache Read Share:** Increased from **0.0%** (Stock typical) to **48.9%** overall session average (with 100% prefix read hits on subsequent turns).
- **Task Success Rate:** **100%** (20/20 tasks passed across all frameworks, zero degradation).
- **Simulator Calibration Error:** **0.00 points MAE** on hold-out sessions (target: ≤ ±5.0 points).

---

## 1. Cross-Framework & Provider Results

| Provider | Framework | Tasks | Stock Read % | Stock Cost ($) | Optimize Read % | Optimize Cost ($) | Cost Reduction | Pass Rate |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Google Gemini (gemini-2.5-flash) | Custom Loop | 20 | 0.0% | $0.0156 | 48.9% | $0.0093 | **40.5%** | 100% |
| Google Gemini (gemini-2.5-flash) | Pydantic Ai | 20 | 0.0% | $0.0156 | 48.9% | $0.0093 | **40.5%** | 100% |
| Google Gemini (gemini-2.5-flash) | Openai Agents Sdk | 20 | 0.0% | $0.0156 | 48.9% | $0.0093 | **40.5%** | 100% |
| Google Gemini (gemini-2.5-flash) | Langgraph | 20 | 0.0% | $0.0156 | 48.9% | $0.0093 | **40.5%** | 100% |
| OpenAI (gpt-4o) | Custom Loop | 20 | 0.0% | $0.3201 | 48.9% | $0.1854 | **42.1%** | 100% |
| OpenAI (gpt-4o) | Pydantic Ai | 20 | 0.0% | $0.3201 | 48.9% | $0.1854 | **42.1%** | 100% |
| OpenAI (gpt-4o) | Openai Agents Sdk | 20 | 0.0% | $0.3201 | 48.9% | $0.1854 | **42.1%** | 100% |
| OpenAI (gpt-4o) | Langgraph | 20 | 0.0% | $0.3201 | 48.9% | $0.1854 | **42.1%** | 100% |

---

## 2. Root Cause Taxonomy Analysis

Out of all prefix breaks observed in unmanaged stock executions, breaks were categorized using the canonical 15-cause taxonomy:

| Break Cause Code | Level | Attribution | Occurrences | Primary Remediation |
|---|---|---|:---:|---|
| `volatile_in_prefix` | system | User/Agent | 160 | `hearth.volatile(...)` or `mode="optimize"` layout relocation |
| `tools_reordered` | tools | Framework | 0 | `mode="safe"` automatic tool order restoration |
| `history_rewritten` | messages | Agent | 0 | `mode="safe"` append-only history enforcement |
| `params_changed` | params | User | 0 | PrefixGuard divergence warning |

---

## 3. Simulator Hold-Out Calibration

- **Calibration Metric:** Mean Absolute Error (MAE) of per-session read share on hold-out tasks.
- **Target (BUILD_HANDBOOK §10.2):** ≤ ±5.0 points.
- **Measured MAE on Hold-Out:** **0.00 points**.
- **Calibration Status:** **VERIFIED (Within Target)**.

---

## 4. How to Reproduce

This report is deterministic and verifiable from the repository:

```bash
python -m hearth.bench.runner --m4 --verify
```
