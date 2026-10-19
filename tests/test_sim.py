"""Tests for the prototype cache simulator and token estimation."""

from hearth.sim import (
    CacheSimulator,
    compute_calibration_mae,
    count_text_tokens,
)


def test_count_text_tokens() -> None:
    text = "Hello world, this is a test prompt for token estimation."
    tokens = count_text_tokens(text)
    assert tokens > 0
    assert count_text_tokens("") == 0


def test_simulator_prefix_cache_hit() -> None:
    # 2048 min prefix for Gemini
    sim = CacheSimulator(provider="gemini", model="gemini-2.5-flash")

    # Long common prompt to exceed 2048 token minimum
    long_system = "System prompt " + ("instructions and examples. " * 300)
    assert count_text_tokens(long_system) > 2048

    # Call 1: cold start (write)
    res1 = sim.simulate_call(
        call_index=1,
        messages=[{"role": "user", "content": "Turn 1 question"}],
        system=long_system,
        ts=100.0,
    )
    assert res1.predicted_read == 0
    assert res1.predicted_write > 0
    assert res1.predicted_read_share == 0.0

    # Call 2: turn 2 with unchanged system prefix and appended turn (read hit)
    res2 = sim.simulate_call(
        call_index=2,
        messages=[
            {"role": "user", "content": "Turn 1 question"},
            {"role": "assistant", "content": "Turn 1 answer"},
            {"role": "user", "content": "Turn 2 question"},
        ],
        system=long_system,
        ts=110.0,
    )
    assert res2.predicted_read > 2048
    assert res2.predicted_read_share > 0.80

    # Call 3: volatile timestamp in system prompt (breaks prefix cache!)
    broken_system = f"Current time: 2026-10-19T12:00:00Z\n{long_system}"
    res3 = sim.simulate_call(
        call_index=3,
        messages=[
            {"role": "user", "content": "Turn 1 question"},
            {"role": "assistant", "content": "Turn 1 answer"},
            {"role": "user", "content": "Turn 2 question"},
            {"role": "assistant", "content": "Turn 2 answer"},
            {"role": "user", "content": "Turn 3 question"},
        ],
        system=broken_system,
        ts=120.0,
    )
    # Since prefix at byte 0 changed, prefix match is 0!
    assert res3.predicted_read == 0
    assert res3.cause == "volatile_in_prefix"


def test_compute_calibration_mae() -> None:
    actual = [0.85, 0.70, 0.90]
    pred = [0.80, 0.75, 0.88]
    mae = compute_calibration_mae(actual, pred)
    # abs diffs: 5, 5, 2 -> mean = 4.0 points
    assert abs(mae - 4.0) < 0.001


def test_simulator_holdout_calibration_target() -> None:
    """M4 Gate requirement: Simulator calibration within +-5 points on holdout."""
    from bench.m0.arms import _execute_agent_simulation
    from bench.tasks.registry import get_all_tasks

    tasks = get_all_tasks()
    # Split into 10 train, 10 hold-out
    holdout_tasks = tasks[10:]
    assert len(holdout_tasks) == 10

    actual_shares: list[float] = []
    pred_shares: list[float] = []

    for task in holdout_tasks:
        for template in ["typical", "minimal"]:
            res = _execute_agent_simulation(
                task=task,
                arm="A",
                template=template,
                replication=1,
                min_prefix_tokens=2048,
            )
            actual_shares.append(res.read_share)

            # Replay through CacheSimulator
            sim = CacheSimulator(provider="gemini", model="gemini-2.5-flash")
            call_shares: list[float] = []
            for idx, step in enumerate(res.steps, start=1):
                sim_res = sim.simulate_call(
                    call_index=idx,
                    messages=step.messages,
                    tools=task.tools,
                    system=step.system_prompt,
                    ts=100.0 + idx * 10.0,
                )
                call_shares.append(sim_res.predicted_read_share)
            pred_session_share = sum(call_shares) / len(call_shares) if call_shares else 0.0
            pred_shares.append(pred_session_share)

    mae = compute_calibration_mae(actual_shares, pred_shares)
    assert mae <= 5.0, f"Simulator calibration target missed: {mae:.2f} points (> 5.0 points)"
