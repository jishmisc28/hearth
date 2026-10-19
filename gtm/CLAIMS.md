# Claims ledger

Public sentences may use only `proven` claims, word for word or narrower. State changes only from evidence in STATUS, BENCH or REPORT on main.

| ID | Claim (exact public wording; fill numbers only from evidence) | Proof | State | Commit / run |
|---|---|---|---|---|
| C-01 | On our 20-task suite, stock <framework> read <X>% of input from the provider cache | M0 bench run | unproven | |
| C-02 | With Hearth, input cost on the same pre-registered tasks fell by <X>% against the stock framework, with no more than 1 task in 20 lost (3 runs each) | M0 bench run | unproven | |
| C-03 | `observe` mode sends byte-identical requests | `test_observe_passthrough_bytes` | unproven | |
| C-04 | `safe` mode adds, removes or changes no message or tool content; it only adds caching metadata and restores order your app already used, and it reports both | `test_safe_no_content_change` | unproven | |
| C-05 | Hearth names the cause of every cache break it detects, and never blames you for TTL, minimum-length or provider misses | `test_break_attribution` | unproven | |
| C-06 | Hearth adds < <X> ms per call at 50k tokens of context | Overhead benchmark in BENCH | unproven | |
| C-07 | On our bench suite, the simulator predicts per-session read share within ±<X> points on held-out sessions | M4 calibration | unproven | |
| C-08 | Agent Cache Efficiency Report v1: <frameworks>, <tasks>, reproducible with `hearth bench --report` | REPORT v1 | unproven | |
| C-09 | In our compaction study, compaction paid for itself after <X> more calls on average; below that it cost more than it saved | M2 compaction study | unproven | |
| C-10 | Works with LangGraph, the OpenAI Agents SDK and Pydantic AI with a one-line change | M3 integration tests | unproven | |
| C-11 | Switch-or-stay saved <X>% on mixed-difficulty tasks with no success loss | M6 bench | unproven | |
