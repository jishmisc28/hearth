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

## Ideas (not scheduled)

(One line each. Nothing here is built without a new D-entry.)
