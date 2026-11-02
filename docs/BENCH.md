# Benchmark & Spend Tracker

Tracks live provider calls, token totals, and spend against approved budget (D-02: $25 for M0 + nightly contract tests, $30 for GTM).

## Budget Status

- **Approved M0 + Contract Test Budget:** $25.00
- **Approved GTM Budget:** $30.00
- **Total Spent to Date:** tokens recorded below; USD not computed (no sourced price for these Bedrock models)

## Spend Log

| Date | Run ID | Target / Provider | Model | Input Tokens | Cached Tokens | Output Tokens | Cost (USD) | Cumulative (USD) |
|---|---|---|---|---|---|---|---|---|
| 2026-11-02 | bedrock-gptoss-smoke | Amazon Bedrock Chat Completions | openai.gpt-oss-120b-1:0 | 84 | 0 (field absent) | 32 | unpriced | unpriced |
| 2026-11-02 | bedrock-gptoss-stable-1 | Amazon Bedrock Chat Completions | openai.gpt-oss-120b-1:0 | 1699 | 0 (field absent) | 8 | unpriced | unpriced |
| 2026-11-02 | bedrock-gptoss-stable-2 | Amazon Bedrock Chat Completions | openai.gpt-oss-120b-1:0 | 1699 | 0 (field absent) | 8 | unpriced | unpriced |
| 2026-11-02 | bedrock-gptoss-clock | Amazon Bedrock Chat Completions | openai.gpt-oss-120b-1:0 | 1716 | 0 (field absent) | 8 | unpriced | unpriced |
| 2026-11-02 | bedrock-hearth-observe | Amazon Bedrock via hearth.wrap observe | openai.gpt-oss-120b-1:0 | 102 | 0 (field absent) | 8 | unpriced | unpriced |
| 2026-11-02 | bedrock-hearth-optimize | Amazon Bedrock via hearth.wrap optimize | openai.gpt-oss-120b-1:0 | 106 | 0 (field absent) | 8 | unpriced | unpriced |
| 2026-11-02 | bedrock-nova-write | Amazon Bedrock Converse | amazon.nova-micro-v1:0 | 2407 | 0 read, 2401 written | 2 | unpriced | unpriced |
| 2026-11-02 | bedrock-nova-read | Amazon Bedrock Converse | amazon.nova-micro-v1:0 | 2407 | 2401 | 2 | unpriced | unpriced |
| 2026-11-02 | bedrock-nova-wrap-write | hearth.wrap observe, Converse | amazon.nova-micro-v1:0 | 3607 | 0 read, 3601 written | 2 | unpriced | unpriced |
| 2026-11-02 | bedrock-nova-wrap-read | hearth.wrap observe, Converse | amazon.nova-micro-v1:0 | 3607 | 3601 | 2 | unpriced | unpriced |

The second identical 1,699-token gpt-oss prompt returned the same usage as the first. No `cached_tokens` field was present. A clock prefixed to that prompt changed the billed input from 1,699 to 1,716. `DeepSeek-V3.1` (`deepseek.v3-v1:0` and `deepseek.v3.1`) was rejected as an invalid model id on this key.

Nova Micro is a different API. Two identical Converse calls with a cache checkpoint: the first wrote 2,401 tokens and the second read 2,401. The same shape through `hearth.wrap` in observe mode wrote 3,601 and then read 3,601. On both pairs the raw `inputTokens` field was 6, which is the uncached tail, not the whole prompt. Input tokens in the table are read + write + that tail. Dollars are blank because `providers.toml` has no sourced price for these models.

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
