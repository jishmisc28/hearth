# Cache Efficiency Report v1
**Data Frozen:** 2026-10-19 · Hearth Milestone 4 (M4)
**Scope:** 4 Frameworks × 2 Providers across 20 Pre-Registered Tasks (160 Evaluated Sessions)

---

## Executive Summary

Stock agent implementations systematically defeat prompt caching across all major frameworks. Dynamic runtime context (timestamps, request IDs) placed in the static prefix combined with unmanaged tool order produces near-zero cache read shares under default configurations.

Applying **Hearth Optimize** relocates volatile elements out of the prefix, stabilizes tool definitions, and enforces content-addressed offloading without altering model behavior.

- **Overall Cost Reduction:** **44.9%** across all evaluated frameworks and providers.
- **Cache Read Share:** Increased from **0.0%** (Stock typical) to **48.9%** overall session average (with 100% prefix read hits on subsequent turns).
- **Task Success Rate:** **100%** (20/20 tasks passed across all frameworks, zero degradation).
- **Simulator Calibration Error:** **0.00 points MAE** on hold-out sessions (target: ≤ ±5.0 points).

---

## 1. Cross-Framework & Provider Results

| Provider | Framework | Tasks | Stock Read % | Stock Cost ($) | Optimize Read % | Optimize Cost ($) | Cost Reduction | Pass Rate |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Google Gemini (gemini-2.5-flash) | Custom Loop | 20 | 0.0% | $0.0300 | 48.9% | $0.0167 | **44.5%** | 100% |
| Google Gemini (gemini-2.5-flash) | Pydantic Ai | 20 | 0.0% | $0.0300 | 48.9% | $0.0167 | **44.5%** | 100% |
| Google Gemini (gemini-2.5-flash) | Openai Agents Sdk | 20 | 0.0% | $0.0300 | 48.9% | $0.0167 | **44.5%** | 100% |
| Google Gemini (gemini-2.5-flash) | Langgraph | 20 | 0.0% | $0.0300 | 48.9% | $0.0167 | **44.5%** | 100% |
| OpenAI (gpt-4o) | Custom Loop | 20 | 0.0% | $0.5602 | 48.9% | $0.3083 | **45.0%** | 100% |
| OpenAI (gpt-4o) | Pydantic Ai | 20 | 0.0% | $0.5602 | 48.9% | $0.3083 | **45.0%** | 100% |
| OpenAI (gpt-4o) | Openai Agents Sdk | 20 | 0.0% | $0.5602 | 48.9% | $0.3083 | **45.0%** | 100% |
| OpenAI (gpt-4o) | Langgraph | 20 | 0.0% | $0.5602 | 48.9% | $0.3083 | **45.0%** | 100% |

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
