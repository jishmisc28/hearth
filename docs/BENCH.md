# Benchmark & Spend Tracker

Tracks live provider calls, token totals, and spend against approved budget (D-02: $25 for M0 + nightly contract tests, $30 for GTM).

## Budget Status

- **Approved M0 + Contract Test Budget:** $25.00
- **Approved GTM Budget:** $30.00
- **Total Spent to Date:** $0.00910820 priced. One Claude Haiku 4.5 call is listed in tokens only, because that model has no price row.

## Spend Log

| Date | Run ID | Target / Provider | Model | Input Tokens | Cached Tokens | Output Tokens | Cost (USD) | Cumulative (USD) |
|---|---|---|---|---|---|---|---|---|
| 2026-11-02 | bedrock-gptoss-smoke | Amazon Bedrock Chat Completions | openai.gpt-oss-120b-1:0 | 84 | 0 (field absent) | 32 | 0.00003180 | 0.00003180 |
| 2026-11-02 | bedrock-gptoss-stable-1 | Amazon Bedrock Chat Completions | openai.gpt-oss-120b-1:0 | 1699 | 0 (field absent) | 8 | 0.00025965 | 0.00029145 |
| 2026-11-02 | bedrock-gptoss-stable-2 | Amazon Bedrock Chat Completions | openai.gpt-oss-120b-1:0 | 1699 | 0 (field absent) | 8 | 0.00025965 | 0.00055110 |
| 2026-11-02 | bedrock-gptoss-clock | Amazon Bedrock Chat Completions | openai.gpt-oss-120b-1:0 | 1716 | 0 (field absent) | 8 | 0.00026220 | 0.00081330 |
| 2026-11-02 | bedrock-hearth-observe | Amazon Bedrock via hearth.wrap observe | openai.gpt-oss-120b-1:0 | 102 | 0 (field absent) | 8 | 0.00002010 | 0.00083340 |
| 2026-11-02 | bedrock-hearth-optimize | Amazon Bedrock via hearth.wrap optimize | openai.gpt-oss-120b-1:0 | 106 | 0 (field absent) | 8 | 0.00002070 | 0.00085410 |
| 2026-11-02 | bedrock-nova-write | Amazon Bedrock Converse | amazon.nova-micro-v1:0 | 2407 | 0 read, 2401 written | 2 | 0.00000049 | 0.00085459 |
| 2026-11-02 | bedrock-nova-read | Amazon Bedrock Converse | amazon.nova-micro-v1:0 | 2407 | 2401 | 2 | 0.00002150 | 0.00087609 |
| 2026-11-02 | bedrock-nova-wrap-write | hearth.wrap observe, Converse | amazon.nova-micro-v1:0 | 3607 | 0 read, 3601 written | 2 | 0.00000049 | 0.00087658 |
| 2026-11-02 | bedrock-nova-wrap-read | hearth.wrap observe, Converse | amazon.nova-micro-v1:0 | 3607 | 3601 | 2 | 0.00003200 | 0.00090858 |
| 2026-11-11 | bedrock-probe-43070714893 | hearth.wrap safe, Converse | amazon.nova-micro-v1:0 | 847 | 0 read, 841 written | 2 | 0.00000049 | 0.00090907 |
| 2026-11-11 | bedrock-probe-43070714893 | hearth.wrap safe, Converse | amazon.nova-micro-v1:0 | 847 | 841 | 2 | 0.00000785 | 0.00091692 |
| 2026-11-11 | bedrock-probe-43070714893 | hearth.wrap safe, Converse | amazon.nova-lite-v1:0 | 847 | 0 read, 841 written | 3 | 0.00000108 | 0.00091800 |
| 2026-11-11 | bedrock-probe-43070714893 | hearth.wrap safe, Converse | amazon.nova-lite-v1:0 | 847 | 841 | 3 | 0.00001370 | 0.00093170 |
| 2026-11-11 | bedrock-probe-43070974414 | hearth.wrap safe, Converse | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 3915 | 0 | 4 | unpriced | 0.00093170 |
| 2026-11-12 | 43261384508 | agent session, 6 turns, then free-tier 429 | gemini-2.5-flash | 86464 | 71570 | 2 | 0.00330885 | 0.00424055 |
| 2026-11-12 | 43261384508 | agent session, 8 turns | amazon.nova-micro-v1:0 | 102467 | 76807 read, 25605 written | 128 | 0.00069191 | 0.00493246 |
| 2026-11-12 | 43261384508 | agent session, 8 turns | amazon.nova-lite-v1:0 | 102467 | 76807 read, 25605 written | 128 | 0.00118615 | 0.00611861 |
| 2026-11-12 | 43264299216 | tool attempt, turn 2 rejected | amazon.nova-micro-v1:0 | 13272 | 0 read, 13266 written | 64 | 0.00000917 | 0.00612778 |
| 2026-11-12 | 43264299216 | tool attempt, turn 2 rejected | amazon.nova-lite-v1:0 | 13272 | 0 read, 13266 written | 56 | 0.00001380 | 0.00614158 |
| 2026-11-12 | 43264432066 | tool attempt, turn 2 rejected | amazon.nova-micro-v1:0 | 13272 | 13266 | 64 | 0.00012525 | 0.00626683 |
| 2026-11-12 | 43264432066 | tool attempt, 3 turns, then rejected | amazon.nova-lite-v1:0 | 39857 | 39817 | 165 | 0.00063926 | 0.00690609 |
| 2026-11-12 | 43264643293 | tool session, 6 turns | amazon.nova-micro-v1:0 | 81438 | 79791 | 509 | 0.00082708 | 0.00773317 |
| 2026-11-12 | 43264643293 | tool session, 6 turns | amazon.nova-lite-v1:0 | 81112 | 79700 | 395 | 0.00137503 | 0.00910820 |

The second identical 1,699-token gpt-oss prompt returned the same usage as the first. No `cached_tokens` field was present. A clock prefixed to that prompt changed the billed input from 1,699 to 1,716. `DeepSeek-V3.1` (`deepseek.v3-v1:0` and `deepseek.v3.1`) was rejected as an invalid model id on this key.

Nova Micro is a different API. Two identical Converse calls with a cache checkpoint: the first wrote 2,401 tokens and the second read 2,401. The same shape through `hearth.wrap` in observe mode wrote 3,601 and then read 3,601. On both pairs the raw `inputTokens` field was 6, which is the uncached tail, not the whole prompt. Input tokens in the table are read + write + that tail.

The US East price list published 2026-11-11 prices Nova cache reads at 0.25× the normal input price and Nova cache writes at $0. gpt-oss has an input and output price and no cache-read price. Its six calls cost $0.00085410 and saved $0, because the responses had no cache fields.

On 2026-11-12 run `43261384508` sent one agent session: the same long instructions, a new short question each turn, then one changed instruction. Turn counts and dollars are the session rows below. The per-turn counts are in `bench/live/2026-11-12.json`. Gemini stopped after six turns with a free-tier 429. Nova finished eight turns, and the changed instruction cleared the cache read.

The same day, a tool session kept that checkpoint on the instructions and sent three tools. The first two attempts were rejected by Nova with HTTP 424, an invalid tool sequence, after the cache had been written. Those calls cost $0.00078748. Run `43264643293` then completed six turns on Nova Micro and Nova Lite. Turn 1 read the 13,266 tokens written by the first attempt. The sixth turn changed one tool description and the cache read stayed: 13,336 of 13,884 on Nova Micro, and 13,300 of 13,776 on Nova Lite. The per-turn counts are in `bench/live/2026-11-12-tools.json`. This run added $0.00220211.

On 2026-11-11 a manual probe under a $1 ceiling called Nova again and tried Claude. Nova Micro's two calls cost $0.00000834 against an uncached pair of $0.00005986. Nova Lite's two calls cost $0.00001478 against $0.00010308. On each second call, 841 of 847 input tokens were a cache read. Claude Haiku 5.5 returned HTTP 403, not enabled for this account. Claude 3 Haiku and Claude 3.5 Haiku returned HTTP 404, end of life. Claude Haiku 4.5 answered once: 3,915 input tokens and no cache write, short of that model's 4,096-token cache minimum. The next Haiku 4.5 call returned HTTP 404 asking for the Anthropic use-case form. No dollar figure is stated for that call.

## Pre-Registered M0 Tasks & Models

- **Pre-Registered Date:** 2026-10-19
- **Provider / Family:** Google Gemini (Gemini 2.5 Flash / Gemini 2.0 Flash)
- **Frameworks:**
  1. Custom loop with Gemini client (`google-genai` / REST)
  2. Pydantic AI with Gemini model
  3. Structured loop / Agent pattern with Gemini
- **Templates:**
  - Minimal: Static instructions only
  - Typical: Includes timestamp/date and user context block
- **Tasks (20):**
  1. `repo_search`: search codebase for symbol definition
  2. `test_fix`: diagnose failing unit test and propose patch
  3. `api_refactor`: refactor API endpoint handler with schema validation
  4. `doc_generate`: generate API documentation from type definitions
  5. `sql_query`: translate natural language to SQL schema query
  6. `log_analysis`: find root cause error from stack trace logs
  7. `config_migrate`: migrate yaml configuration to toml schema
  8. `json_filter`: extract and summarize nested json payloads
  9. `cli_help`: generate command-line interface arguments and help strings
  10. `regex_builder`: generate and validate complex regex pattern
  11. `lint_fix`: correct ruff and mypy errors in python module
  12. `git_conflict`: resolve merge conflict between two file revisions
  13. `mock_gen`: generate mock test fixtures for external service
  14. `dep_audit`: identify outdated dependencies from lockfile
  15. `security_scan`: detect hardcoded secrets or sql injection flaws
  16. `perf_opt`: optimize tight algorithmic loop with profiling data
  17. `schema_validate`: validate input against pydantic schema
  18. `error_handling`: add graceful retry and error handling to network call
  19. `multi_step_math`: compute financial ledger reconciliation
  20. `code_review`: provide structured code review on pull request diff
