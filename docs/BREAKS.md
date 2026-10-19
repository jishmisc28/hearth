# Prompt Cache Break Taxonomy & Cause Registry

Generated from `src/hearth/data/breaks.yaml` per `BUILD_HANDBOOK.md` §5.2 and Milestone 2.

Hearth's `PrefixGuard` inspects successive API calls in a session, compares prompt prefix tokens against prior turns, and evaluates divergence causes **in strict precedence order** (first match wins).

---

## 1. Summary Taxonomy & Precedence Table

| Precedence | Cause Code | Level | User-Caused? | Detected When | Hearth Mitigation |
|---|---|---|---|---|---|
| **1** | `below_minimum` | system | No | Prefix shorter than provider minimum | Automatically skipped |
| **2** | `short_session` | system | No | Session ends before reuse | Planner skips write fee |
| **3** | `ttl_expired` | system | No | Elapsed time > TTL | 1-hour TTL / `expect_pause()` |
| **4** | `provider_miss` | system | No | Valid prefix missed by backend | Logged; never blamed on user |
| **5** | `params_changed` | system | Yes | Model, temp, tool_choice altered | Isolate per session / subagents |
| **6** | `tools_changed` | tools | Yes | Tool schemas added/removed/edited | Static registration at start |
| **7** | `tools_reordered` | tools | Yes | Same tools in different order | `safe` restores first-seen order |
| **8** | `volatile_in_prefix` | system | Yes | Timestamps, UUIDs, git hashes | `volatile()` or `optimize` relocation |
| **9** | `system_changed` | system | Yes | System prompt altered mid-session | Relocate updates to tail |
| **10** | `session_mutated` | session | Yes | Memory fact injected mid-session | Queue for next session |
| **11** | `image_toggled` | messages | Yes | Image added/removed earlier in turns | Confine media to active turn |
| **12** | `history_rewritten` | messages | Yes | Messages modified or truncated | Append-only / planned compaction |
| **13** | `no_breakpoints` | system | Yes | Explicit breakpoints missing | `safe` injects breakpoints |
| **14** | `metadata_dropped` | system | Framework | Middleware stripped cache fields | Trace diagnostic with version |
| **15** | `cold_subagent` | system | Design | Subagent prefix completely cold | Share common prefix with parent |

---

## 2. Invariant Rules for Attribution (INV-10)

Per `BUILD_HANDBOOK.md` INV-10:
> **INV-10**: `below_minimum`, `short_session`, `ttl_expired`, and `provider_miss` are **NEVER** reported as user-caused.

When evaluating developer metrics:
- Environmental, platform, and backend cache dropouts are isolated from application-level invalidations.
- Only application-level defects (`tools_reordered`, `volatile_in_prefix`, `history_rewritten`, etc.) contribute to user-caused break counts and actionable developer warnings.

---

## 3. Detailed Cause Reference

### 1. `below_minimum`
- **Condition**: Total prefix tokens $< \text{provider\_threshold}$ (e.g. 2,048 tokens on Gemini, 1,024 tokens on Anthropic, 1,024 on OpenAI).
- **Impact**: Zero caching savings; request dispatched as full uncached input.
- **Remediation**: None needed; Hearth avoids setting cache control headers to prevent unneeded write processing.

### 2. `short_session`
- **Condition**: Single-turn call where no subsequent turn occurs before session termination.
- **Impact**: Paying a cache creation/write markup (e.g. 1.25×) with 0 read benefit.
- **Remediation**: The cache planner uses session history or `s.expect_calls(n)` hints to omit cache breakpoints on predicted one-shot runs.

### 3. `ttl_expired`
- **Condition**: Idle duration between consecutive turn invocations exceeds provider cache TTL (e.g. 5 minutes).
- **Impact**: Cold cache miss on all prefix tokens.
- **Remediation**: Use Hearth's 1-hour TTL on stable breakpoints or application `s.expect_pause()` hints before long human approvals.

### 4. `provider_miss`
- **Condition**: Exact byte-identical prefix submitted within TTL window, yet provider reported `read_tokens == 0`.
- **Impact**: Unexpected latency spike and cache re-write cost.
- **Remediation**: Tracked in SQLite ledger and trace logs under provider health telemetry; never flagged as user error.

### 5. `params_changed`
- **Condition**: Decoding parameters (`temperature`, `top_p`, `model`, `tool_choice`) changed across turns.
- **Impact**: Providers partition cache keys by configuration hash; invalidates 100% of the prompt.
- **Remediation**: Maintain constant execution parameters for a given conversation session.

### 6. `tools_changed`
- **Condition**: Tools added, removed, or schemas modified between dialogue turns.
- **Impact**: Because tools precede dialogue messages in most provider token streams, editing tools invalidates all downstream prompt cache.
- **Remediation**: Declare all available tools upfront; use `tool_addition` only where supported natively by providers.

### 7. `tools_reordered`
- **Condition**: Identical tool suite provided, but serialized in a different order due to non-deterministic dictionary traversal.
- **Impact**: Byte-exact cache mismatch at prefix byte 0.
- **Remediation**: `hearth.wrap(..., mode="safe")` remembers the first-seen tool order and automatically re-indexes outgoing tool arrays.

### 8. `volatile_in_prefix`
- **Condition**: Timestamps, ISO dates, session counters, or git hashes embedded in the system prompt or static prefix.
- **Impact**: Invalidates all tokens following byte offset 0.
- **Remediation**: Use `hearth.volatile(text)` or run in `mode="optimize"`, which relocates volatile lines to the dynamic user message tail.

### 9. `system_changed`
- **Condition**: Instructional text in the system prompt altered mid-session.
- **Impact**: Total cache invalidation from the modified byte index onward.
- **Remediation**: Append updates into the user dialogue turn rather than editing the base system prompt.

### 10. `session_mutated`
- **Condition**: Dynamic facts or external retrieval results injected into early session segments.
- **Impact**: Forces rewriting of subsequent turns.
- **Remediation**: Buffer dynamic facts for the turn tail; promote to static session prefix only upon starting a fresh session.

### 11. `image_toggled`
- **Condition**: Multimodal images inserted or stripped in historical conversation turns.
- **Impact**: Token length shifting and prefix cache eviction.
- **Remediation**: Confine image payloads to the specific turn where visual analysis is performed.

### 12. `history_rewritten`
- **Condition**: Earlier dialogue turns deleted or altered (e.g. naive sliding window truncating turn 0).
- **Impact**: Shifting dialogue turns changes prefix byte 0, causing complete cache loss across the entire multi-turn context.
- **Remediation**: Maintain append-only conversation history, or execute Hearth planned compaction at payback-positive boundaries.

### 13. `no_breakpoints`
- **Condition**: Explicit caching provider (such as Anthropic Messages API) called without `cache_control` breakpoints.
- **Impact**: Provider handles the request as standard uncached input.
- **Remediation**: `mode="safe"` calculates optimal breakpoint placement and injects `{"type": "ephemeral"}` blocks within provider limits.

### 14. `metadata_dropped`
- **Condition**: Framework abstraction dropped vendor-specific caching headers or properties during message mapping.
- **Impact**: Request reaches provider without necessary caching instructions.
- **Remediation**: Hearth logs diagnostic telemetry noting the framework version and missing fields.

### 15. `cold_subagent`
- **Condition**: Ephemeral subagent initiated with unique instructions that cannot reuse parent cache blocks.
- **Impact**: Every subagent starts at zero read share.
- **Remediation**: Standardize a shared static preamble across parent and subagent prompts.
