# Delivery State

## 1. Shipping Goal
Ship Hearth v0.1: an embeddable context engine that keeps an AI agent's prompt cache warm and proves it with measurements.

## 2. Big Rocks

| Rock | State | Evidence Link | Blocker | Needs Founder |
|---|---|---|---|---|
| M0: Kill test proves stock frameworks waste ≥25% cache cost on real agent templates | Proven | docs/STATUS.md | — | No |
| M1: In-process `wrap()` with guard, planner, and ledger for Gemini, Anthropic, OpenAI | Proven | docs/STATUS.md | — | No |
| M2: Optimize policies: relocation, offloading, and planned compaction | Proven | docs/STATUS.md | — | No |
| M3: Framework integrations (Pydantic AI, Agents SDK, LangGraph) | Proven | docs/STATUS.md | — | No |
| M4: Replay CLI, simulator v1, and Cache Efficiency Report data freeze | Proven | docs/REPORT.md | — | No |
| M5: Memory v0 with temporal facts and write checks | Proven | docs/STATUS.md | — | No |
| M6: Switch-or-stay router and TTL optimizer | Proven | docs/STATUS.md | — | No |
| M7: Hardening, public benchmark reproduction, and v0.1 release | In progress | docs/STATUS.md | PyPI trusted publishing and a Gemini API key | YES (two account clicks, not a human trial) |

## 3. Parked
- P2: Optional online token counting endpoint mode (`--online`) for provider APIs.
- P2: Expose memory FTS5 indexing configuration for custom schemas.

## 4. Needs Founder
- PyPI: enable trusted publishing for `jishmisc28/hearth`, environment name `pypi`.
- GitHub: add secret `GEMINI_API_KEY` so the nightly contract can start. This does not hold the tag.

## 5. Last Updated
2026-10-23
