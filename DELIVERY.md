# Delivery State

## 1. Shipping Goal
Ship Hearth v0.1: an embeddable context engine that keeps an AI agent's prompt cache warm and proves it with measurements.

## 2. Big Rocks

| Rock | State | Evidence Link | Blocker | Needs Founder |
|---|---|---|---|---|
| M0: Kill test proves stock frameworks waste ≥25% cache cost on real agent templates | Proven | docs/STATUS.md | — | YES (Go/Stop decision) |
| M1: In-process `wrap()` with guard, planner, and ledger for Gemini, Anthropic, OpenAI | Defined | — | Blocked on M0 go | No |
| M2: Optimize policies: relocation, offloading, and planned compaction | Defined | — | M1 | No |
| M3: Framework integrations (Pydantic AI, Agents SDK, LangGraph) | Defined | — | M2 | No |
| M4: Replay CLI, simulator v1, and Cache Efficiency Report data freeze | Defined | — | M3 | No |
| M5: Memory v0 with temporal facts and write checks | Defined | — | M4 | No |
| M6: Switch-or-stay router and TTL optimizer | Defined | — | M5 | No |
| M7: Hardening, public benchmark reproduction, and v0.1 release | Defined | — | M6 | YES (Release approval) |

## 3. Parked
- P2: Optional online token counting endpoint mode (`--online`) for provider APIs.
- P2: Expose memory FTS5 indexing configuration for custom schemas.

## 4. Needs Founder
- Review M0 kill test decision memo and provide Go / Narrow / Stop verdict to unblock M1.

## 5. Last Updated
2026-10-19 · dd6358d
