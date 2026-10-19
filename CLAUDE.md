# CLAUDE.md: rules for any coding agent in this repo

(Symlink `AGENTS.md` to this file.)

## What this is

Hearth is a Python library that keeps an AI agent's prompt cache warm. It is **not** an agent framework, gateway, hosted service or UI.

**Source of truth, in order:**
1. `docs/BUILD_HANDBOOK.md` (spec, invariants, plan);
2. the newest entry in `docs/STATUS.md`;
3. `docs/DECISIONS.md`.

The GTM thread follows `gtm/GTM_HANDBOOK.md`.

## Scope fence (hard)

- Build only the current milestone in BUILD_HANDBOOK §10. Anything in §7 "Not doing" needs Abhranshu's written OK, recorded in DECISIONS.
- The core package has **zero required dependencies**. New dependencies go into an extra, and only with a DECISIONS entry (reason, size, licence).
- No new top-level directories. No new docs except `docs/METRICS.md` (M1), `docs/BREAKS.md` (M2, generated from `breaks.yaml`), `docs/BENCH.md` (M0) and `docs/REPORT.md` (M4).
- Provider facts (prices, minimums, TTLs, limits) live only in `src/hearth/data/providers.toml`, each with a source URL and date. Never hard-code them.

## How to work

1. **Pick.** Take the next task in the current milestone. Write one line saying what "done" means.
2. **Test first.** If it touches an invariant (§8), write the named test first. A missing named test fails CI.
3. **Build small.** Use `uv`; `ruff`, `mypy --strict` (core) and `pytest` must pass before every commit (`make check`).
4. **Commit.** Conventional commits, one logical change each.
5. **Gate.** At each gate:
   - run the gate commands;
   - paste the output tails into STATUS (format below);
   - have a fresh reviewer subagent on the strongest model review the milestone diff against the handbook;
   - fix its findings or record why not.
6. **Report.** Every Friday, add a STATUS entry at the top of the Log, even if mid-milestone.

## Correctness rules that are easy to get wrong

- **`observe` is byte-identical.** Never "improve" a request in `observe` mode.
- **`safe` is content-equivalent.** Same messages, same tools, same text; only serialisation may change.
- **Append-only.** Never rewrite an already-sent message except through a recorded compaction event.
- **Fail-open.** Any internal exception sends the original request unchanged and records `hearth_error`.
- **Exact usage reconciliation.** Read + write + uncached must equal the provider's total input, per provider rules.
- **No content in the ledger, logs or spans** unless recording is explicitly enabled.
- **Cost arithmetic uses `Decimal`** or integer micro-units, never float.
- **Attribution.** A cache miss caused by TTL expiry, below-minimum length or the provider is never reported as the user's fault.

## Spending money

- Live provider calls cost Abhranshu money. The M0 kill test and nightly contract tests run on the budget he approved (BUILD_HANDBOOK §10). Use the smallest suitable model.
- Log every live run's token totals in `docs/BENCH.md`.
- **Stop and ask before exceeding the approved budget.**

## Stop and ask Abhranshu (otherwise keep going)

- **At M0 start:** approve the API budget (D-02); confirm the GitHub owner (`jishmisc28` or `ab-atnms`); confirm the PyPI name `hearth-ai` is free (fallback `hearth-cache`).
- **At the M1 gate:** whether to make the repo public and tag `0.1.0a1` (D-09).
- **The M0 go/stop decision.** Write the memo and wait.
- **Public interfaces.** Anything that changes a documented interface: Python API, CLI flags, ledger schema, metric definitions.
- **Releases.** Before any release, PyPI upload, or making the repo public.
- **Failed gates.** A gate that fails after two genuine attempts: write the evidence and propose a cut from the cut line.

## Never

- Post, email, DM or comment anywhere public; open issues or PRs in other projects; create accounts.
- Put real API keys, prompts or customer data in fixtures or commits.
- Read or edit anything outside this repo except `~/.hearth/`. `gtm/private/` is gitignored and never read by the build agent.
- Write marketing claims in code docs. Product claims live in `gtm/` and go through `gtm/CLAIMS.md`.

## Parallel threads

- **The GTM thread** works in a git worktree on branch `gtm` and edits only `gtm/`.
- **The build thread** never edits `gtm/`. It reads GTM files with `git show gtm:<path>`, and merges `gtm` into `main` at M7.
- **Subagents.** Use them on cheaper models for independent, well-specified work: adapters' boilerplate, task fixtures, CLI formatting, docs. Core layout, guard, planner and simulator logic is written or reviewed by the strongest model.

## STATUS entry format

```markdown
## YYYY-MM-DD · M<k> <name>: VERIFIED | IN PROGRESS | BLOCKED | PENDING-HUMAN
Gate commands and output tails:
Numbers: tests passed · read share / cost ratio / TTFT p50 (if measured) · API spend this week
What changed (user-visible first): 3–6 bullets
Learned (for Abhranshu): 2–3 bullets explaining one real concept, with file:line pointers
GTM-ready: which claims or assets this unlocks (claim IDs)
Blocked on Abhranshu: the exact question, or "nothing"
```
