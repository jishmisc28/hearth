"""Performance overhead benchmark verifying NFR-1 latency budget (BUILD_HANDBOOK §5.1)."""

import time

from hearth.wrapper import WrappedMethod


def test_nfr1_safe_mode_latency_budget() -> None:
    """NFR-1: added latency in safe mode is p50 <= 2 ms and p99 <= 5 ms at 50k tokens."""
    # Build 50k tokens of realistic context (approx 200k characters across 30 messages)
    paragraph = (
        "def process_data(records: list[dict]) -> None:\n"
        "    # Optimized batch pipeline\n"
        "    for r in records:\n"
        "        validate(r)\n" * 40
    )
    messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Step {i}: {paragraph}"}
        for i in range(30)
    ]
    tools = [
        {
            "name": f"tool_{i}",
            "description": f"Tool description {i}",
            "parameters": {"type": "object"},
        }
        for i in range(10)
    ]

    wrapper = WrappedMethod(
        target_fn=lambda *a, **kw: None,
        provider="gemini",
        api="generate_content",
        mode="safe",
        record=False,
        strict=False,
    )

    kwargs = {
        "model": "gemini-2.5-flash",
        "system": "System instructions with guidelines",
        "tools": tools,
        "messages": messages,
    }

    import gc

    gc.collect()

    # Warmup
    for _ in range(15):
        wrapper._process_safe_request(kwargs, "perf-session")

    durations_ms: list[float] = []
    gc.disable()
    try:
        for _ in range(100):
            t0 = time.perf_counter()
            wrapper._process_safe_request(kwargs, "perf-session")
            t1 = time.perf_counter()
            durations_ms.append((t1 - t0) * 1000.0)
    finally:
        gc.enable()

    durations_ms.sort()
    n = len(durations_ms)
    p50 = durations_ms[int(n * 0.50)]
    p99 = durations_ms[min(int(n * 0.99), n - 2)]

    print(f"\n[NFR-1 Benchmark at ~50k tokens] p50: {p50:.3f} ms, p99: {p99:.3f} ms")

    # Budget: p50 <= 2.0 ms, p99 <= 5.0 ms
    assert p50 <= 2.0, f"NFR-1 missed: p50 is {p50:.3f} ms (> 2.0 ms)"
    assert p99 <= 5.0, f"NFR-1 missed: p99 is {p99:.3f} ms (> 5.0 ms)"
