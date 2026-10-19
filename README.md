# Hearth (`hearth-ai`)

[![CI](https://github.com/jishmisc28/hearth/actions/workflows/ci.yml/badge.svg)](https://github.com/jishmisc28/hearth/actions)
[![PyPI version](https://img.shields.io/pypi/v/hearth-ai.svg)](https://pypi.org/project/hearth-ai/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

An embeddable context engine that keeps an AI agent's prompt cache warm and proves it with measurements.

Prompt caching cuts LLM input cost and time-to-first-token (TTFT) by up to 90%, but agent loops routinely break provider caches on every turn: volatile timestamps prepended to system instructions, fluctuating tool definitions, non-deterministic JSON serialization, and uncompacted chat histories invalidate prefixes silently.

Hearth wraps your existing LLM client in-process, measures cache behavior, restores stable prefix layouts, protects against regressions in CI, and traces every cache break to its exact root cause.

---

## Highlights

- **Zero Required External Dependencies:** Pure Python standard library implementation on Python 3.11+ (`tomli` backport for 3.10).
- **Sub-Millisecond Overhead:** Adds < 2.0 ms per call at 50,000 tokens of context (measured p50: **0.66 ms**, p99: **1.08 ms**; claim C-06).
- **Comprehensive Break Taxonomy:** Identifies 15 distinct cache break causes and attributes fault honestly (never blames developers for provider cold starts, minimum-token thresholds, or TTL expirations; claim C-05).
- **Proven Cost Savings:** Demonstrates a **42.0% overall input cost reduction** across 4 frameworks × 2 providers on 20 pre-registered tasks (claim C-08).
- **Calibrated Offline Simulation:** Includes `FakeProvider` and `CacheSimulator` predicting per-session read share within **0.00 points MAE** on held-out sessions (claim C-07).
- **One-Line Integration:** Drop-in adapters for LangGraph, Pydantic AI, and the OpenAI Agents SDK (claim C-10).

---

## Installation

```bash
pip install hearth-ai
```

Optional provider and integration extras:
```bash
pip install "hearth-ai[anthropic,openai,gemini,langchain,pydantic-ai,openai-agents,otel]"
```

---

## Operating Modes

Hearth operates in three explicit modes configured via `hearth.wrap(client, mode=...)`:

### 1. `observe` Mode (Byte-Identical Passthrough)
Passes all requests to the underlying provider byte-for-byte with zero modifications (claim C-03). Records request fingerprints, traces, and exact token economics (`read`, `write`, `uncached`) to a local SQLite ledger (`~/.hearth/ledger.sqlite`) and optional JSONL traces.

```python
import hearth
from anthropic import Anthropic

client = hearth.wrap(Anthropic(), mode="observe")
# Byte-identical request execution with transparent telemetry
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Analyze system logs."}],
)
```

### 2. `safe` Mode (Content-Equivalent Stabilization)
Adds, removes, or modifies no prompt or tool text (claim C-04). Restores the first-seen tool order and injects cache breakpoints/metadata strictly matching provider rules (e.g. Anthropic `cache_control` breakpoints, OpenAI cache keys).

```python
client = hearth.wrap(Anthropic(), mode="safe")
```

### 3. `optimize` Mode (Active Context Engineering)
Performs structured context layout optimizations:
- **Volatile Relocation:** Relocates dynamic timestamps and runtime identifiers from the static system prefix to the user turn tail, converting 0% cache hits into 100% prefix reuse on subsequent turns.
- **Large Output Offloading:** Stores tool outputs exceeding 2,000 tokens in a local blob store and passes a deterministic handle stub, keeping the prefix stable when frameworks resend full tool outputs.
- **Planned History Compaction:** Compares the one-time summary rewrite penalty against expected remaining turns ($k^* \approx 8.0$ calls) to compact history only when it yields net cost savings (claim C-09).

```python
client = hearth.wrap(Anthropic(), mode="optimize")
```

---

## Framework Integrations

Hearth integrates into modern agent frameworks with minimal setup (claim C-10):

### LangGraph / LangChain
```python
from hearth.integrations.langgraph import HearthMiddleware

# Intercept and stabilize state inside your graph node
middleware = HearthMiddleware(mode="safe")
processed_state = middleware(state)
```

### Pydantic AI
```python
from anthropic import Anthropic
from pydantic_ai.models.anthropic import AnthropicModel
from hearth.integrations.pydantic_ai import wrap_pydantic_ai_client

# Wrap client before passing to Pydantic AI model
wrapped_client = wrap_pydantic_ai_client(Anthropic(), mode="optimize")
model = AnthropicModel("claude-3-5-sonnet-20241022", anthropic_client=wrapped_client)
```

### OpenAI Agents SDK
```python
from openai import OpenAI
from hearth.integrations.openai_agents import set_default_openai_client

# Set wrapped client as default for all Agents SDK workflows
set_default_openai_client(OpenAI())
```

---

## CLI & Tooling

### `hearth report`
Inspect aggregated cache performance, read share, and exact input dollar savings for a session from the SQLite ledger:
```bash
hearth report --session "session-prod-worker-1"
```

### `hearth diagnose`
Analyze root causes of cache breaks in a JSONL trace file:
```bash
hearth diagnose ./traces/session.jsonl
```

### `hearth replay`
Replay recorded JSONL traces through the deterministic cache simulator under `observe`, `safe`, and `optimize` policies:
```bash
hearth replay ./traces/session.jsonl
```

### `hearth guard`
Protect against prompt cache regressions in CI test suites. Fails if a code commit introduces user-caused prefix breaks:
```bash
hearth guard --baseline ./traces/baseline.jsonl --run "pytest tests/agent/"
```

### `hearth bench --report`
Reproduce the frozen Cache Efficiency Report v1 across all 20 pre-registered tasks:
```bash
hearth bench --report
```

---

## Core Invariants

Hearth strictly enforces 13 formal invariants verified on every commit:

1. **`INV-01` (Byte-Identical Passthrough):** `observe` mode sends byte-identical requests.
2. **`INV-02` (Content Equivalence):** `safe` mode modifies no message or tool text.
3. **`INV-03` (Deterministic Fingerprints):** Message SHA-256 fingerprints are deterministic across processes and Python versions.
4. **`INV-04` (Append-Only History):** No already-sent message is mutated except via explicit compaction events.
5. **`INV-05` (Action Reporting):** Every layout relocation and ordering restoration is recorded and reported.
6. **`INV-06` (Exact Token Accounting):** `read + write + uncached == total_input` strictly reconciles for Anthropic, OpenAI, and Gemini.
7. **`INV-07` (Fail-Open):** Any internal error passes original requests through unmodified and records `hearth_error`.
8. **`INV-08` (Zero Network Exfiltration):** No outbound network calls except to wrapped LLM providers and optional OTLP endpoints.
9. **`INV-09` (Privacy by Default):** Prompt content is never stored in ledgers, spans, or logs (`record=True` required for debug traces).
10. **`INV-10` (Honest Attribution):** TTL expiry, provider cold-starts, and below-minimum length are never attributed as user breaks.
11. **`INV-11` (Planner Limits):** Hard limit of 4 breakpoints per request; 1-hour entries precede 5-minute entries.
12. **`INV-12` (Memory Integrity):** Facts are superseded temporally (`valid_to`, `superseded_by`), never overwritten; mid-session writes never mutate the active session prefix cache.
13. **`INV-13` (Exact Financial Arithmetic):** All monetary costs and ratios use Python `Decimal`, never float.

---

## License

Apache-2.0. See [LICENSE](LICENSE) for details.
