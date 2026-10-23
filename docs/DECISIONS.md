# Decisions

Append only. Format: ID · date · decision · why · reversal trigger. OPEN rows are resolved by appending a new row that names the row it resolves.

| ID | Date | Decision | Why | Reversal trigger |
|---|---|---|---|---|
| D-00 | 2026-10-16 | Build Hearth (cache-aware context engine) instead of Pawl | Fresh landscape scan: largest measurable win, least-owned space, covers memory, routing, latency and evaluation in one design | M0 kill test fails |
| D-01 | OPEN | GitHub owner: `jishmisc28` or `ab-atnms` | Abhranshu decides at M0 | — |
| D-02 | OPEN | API budget: proposed $100–300 for M0, nightly tests and report runs, plus up to $50 for GTM reproductions | Live measurements cost money | Abhranshu approves at M0 |
| D-03 | 2026-10-16 | Python first, zero required dependencies in the core; TypeScript after v0.1 | Runs in the agent's process; agent developers are in Python, then TS; work per call is microseconds against seconds of model time | Strong demand from TS users before v0.1 |
| D-04 | 2026-10-16 | Default mode `safe` (content-equivalent); `optimize` is opt-in | Adoption needs zero behaviour risk | User evidence that `optimize` is safe enough to default |
| D-05 | 2026-10-16 | Provider facts live only in `src/hearth/data/providers.toml`, dated and sourced | Prices and rules change | — |
| D-06 | 2026-10-16 | Package `hearth-ai` (import `hearth`), Apache-2.0; `hearth-sdk` is taken by an unrelated identity product | Name check | `hearth-ai` taken → `hearth-cache` |
| D-07 | 2026-10-16 | No proxy or gateway in v0.1 | Gateways are consolidating; in-process is the wedge | Teams ask for language-neutral use → Go sidecar |
| D-08 | 2026-10-16 | Memory write checks follow BUILD_HANDBOOK §5.7 (size, secrets, instruction-like text, taint), carried over from earlier design work | Self-contained spec | — |
| D-09 | PROPOSED | Make the repo public and tag `0.1.0a1` at the M1 gate | External `diagnose` runs and build-in-public posts need an installable package | Abhranshu says no → public at launch; move GTM week-6 targets to week 10 |
| D-10 | (M1) | OTel attribute names for cache read and cache write, verified against the current GenAI registry | Naming is in flux (`cache_write` vs `cache_creation`) | — |
| D-11 | (M0) | Exact model IDs for the kill test, recorded before any run | Pre-registration | — |
| D-01-R | 2026-10-19 | Resolves D-01: GitHub owner is `jishmisc28` (origin repo `https://github.com/jishmisc28/hearth.git`) | User instruction | Abhranshu reassigns |
| D-02-R | 2026-10-19 | Resolves D-02: API budget approved at $25 for M0 + nightly contract tests, plus $30 for GTM; tracked in `docs/BENCH.md` | User instruction; live measurements cost money | Budget exceeded or increased |
| D-09-R | 2026-10-19 | Resolves D-09: Ask Abhranshu at M1 gate whether to make repo public and tag `0.1.0a1` | User instruction | M1 gate reached |
| D-11-R | 2026-10-19 | Resolves D-11: M0 pre-registered models: Gemini models only (`gemini-2.5-flash` / `gemini-2.0-flash` / `gemini-1.5-flash`) | User instruction: no Claude models; use Gemini family only | User changes model directive |
| D-12 | 2026-10-19 | Sole use of Gemini family models for all agent, subagent, and LLM calls | User instruction: DO NOT use Claude models; use LLM models from your family only | User instruction |
| D-13 | 2026-10-19 | Include `tomli>=1.1.0;python_version<'3.11'` in core dependencies | Python 3.10 lacks `tomllib` in stdlib; on Python 3.11+ zero external dependencies are installed, preserving D-03 | Drop Python 3.10 support |
| D-09-R2 | 2026-10-19 | Resolves D-09: Repository confirmed public on GitHub (`jishmisc28/hearth`); tag `0.1.0a1` created and pushed | Abhranshu approved at M1 gate ("yes to 1") | — |
| D-14 | 2026-10-23 | v0.1.0 is not held for three human install trials. The Gemini evaluation the same night (LIBRARY-OK, offline checks 10/10, recorded in `hearth-v0.1-proof.html`) is the acceptance check. | Founder instruction: agents verify the library. Do not block the release on another person. | A later human trial contradicts that result |
| D-15 | 2026-10-23 | Cut git tag `v0.1.0` on the offline gate. The five-night live contract streak starts when `GEMINI_API_KEY` is in GitHub secrets. No live saving is claimed while `docs/BENCH.md` spend is $0.00. | No provider key is available to the agents. Founder said proceed rather than wait. | A live run shows the offline behavior does not hold |

## Ideas (not scheduled)

(One line each. Nothing here is built without a new D-entry.)

