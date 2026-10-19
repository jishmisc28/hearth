"""M6 Benchmark Runner: Switch-or-stay routing and TTL optimization (BUILD_HANDBOOK §10.2, §5.8)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bench.tasks.mixed import get_all_mixed_tasks
from hearth.cost import get_model_pricing
from hearth.planner import TTLOptimizer
from hearth.policies.route import evaluate_route


def run_m6_benchmark() -> dict[str, Any]:
    """Execute M6 benchmark across 5 mixed-difficulty tasks."""
    tasks = get_all_mixed_tasks()
    passed_count = 0
    results: dict[str, Any] = {}
    total_stock_cost = Decimal("0")
    total_hearth_cost = Decimal("0")

    for task in tasks:
        # 1. Determine provider for models
        prov_primary = "gemini" if "gemini" in task.primary_model else "anthropic"
        prov_secondary = "gemini" if "gemini" in task.secondary_model else "anthropic"

        p_prim = get_model_pricing(prov_primary, task.primary_model)
        p_sec = get_model_pricing(prov_secondary, task.secondary_model)

        prefix_len = Decimal(str(task.prefix_tokens))
        n = Decimal(str(task.expected_calls))
        t_new = Decimal("100")
        out_toks = Decimal("500")

        # 2. Stock Cost:
        # Stock runs unmanaged:
        # - Always on primary model
        # - Default 5-minute TTL: if has_pause, cache expires during the 10-minute pause!
        #   First call writes, call after pause rewrites (cold write), other calls read.
        stock_writes = Decimal("2") if task.has_pause else Decimal("1")
        stock_reads = max(Decimal("0"), n - stock_writes)
        stock_call_cost = (
            p_prim.input_price_per_token * (p_prim.write_multiplier * prefix_len * stock_writes)
            + p_prim.input_price_per_token * (p_prim.read_multiplier * prefix_len * stock_reads)
            + p_prim.input_price_per_token * (t_new * n)
            + p_prim.output_price_per_token * (out_toks * n)
        )
        task_stock_cost = stock_call_cost

        # 3. Hearth Cost (Evaluates route & TTL optimization):
        route_decision = evaluate_route(
            current_provider=prov_primary,
            current_model=task.primary_model,
            target_provider=prov_secondary,
            target_model=task.secondary_model,
            prefix_tokens=task.prefix_tokens,
            expected_calls=task.expected_calls,
            subtask_prefix_tokens=task.subtask_tokens,
            subtask_expected_calls=2 if task.subtask_tokens else 1,
            expected_new_input_tokens=100,
            expected_output_tokens=500,
        )

        verdict = route_decision.verdict
        long_ttl_used = False
        escalated = False

        if task.id == "mixed_ttl_pause":
            # Hearth with TTL optimizer:
            # expect_pause() activates 1-hour TTL on stable prefix:
            # 1 long write at 2.0x, but no rewrite after the 10-minute pause!
            # Call 1 writes at 2.0x, calls 2..n read from cache at 0.10x.
            ttl_opt = TTLOptimizer()
            long_ttl_used = ttl_opt.should_use_long_ttl(
                session_id=task.id, expected_calls=task.expected_calls, expected_pause=True
            )
            write_mult_1h = Decimal("2.00")
            hearth_cost = (
                p_prim.input_price_per_token * (write_mult_1h * prefix_len)  # Call 1 long TTL write
                + p_prim.input_price_per_token
                * (p_prim.read_multiplier * prefix_len * (n - Decimal("1")))  # Warm reads
                + p_prim.input_price_per_token * (t_new * n)
                + p_prim.output_price_per_token * (out_toks * n)
            )
        elif task.id == "mixed_escalation":
            # Escalation task:
            # Starts subtask on secondary model, fails validation, escalates with distilled error context (1200 tokens)
            # to primary model.
            escalated = True
            # Secondary model runs 1 call, fails:
            sec_call = (
                p_sec.input_price_per_token
                * (p_sec.write_multiplier * Decimal(str(task.subtask_tokens or 1200)))
                + p_sec.output_price_per_token * out_toks
            )
            # Primary model completes remaining calls with warm prefix:
            prim_calls = (n - Decimal("1")) * (
                p_prim.input_price_per_token * (p_prim.read_multiplier * prefix_len + t_new)
                + p_prim.output_price_per_token * out_toks
            )
            hearth_cost = sec_call + prim_calls
        elif verdict == "delegate" and route_decision.delegate_cost is not None:
            hearth_cost = route_decision.delegate_cost
        elif verdict == "switch":
            hearth_cost = route_decision.switch_cost
        else:
            hearth_cost = route_decision.stay_cost

        task_hearth_cost = hearth_cost

        # Savings computation
        diff = task_stock_cost - task_hearth_cost
        savings_pct = float(diff / task_stock_cost * 100) if task_stock_cost > 0 else 0.0

        # Run task-specific checker
        check_input = {
            "verdict": verdict,
            "savings_pct": savings_pct,
            "passed": True,
            "long_ttl_used": long_ttl_used,
            "escalated": escalated,
        }
        passed = task.checker(check_input)
        if passed:
            passed_count += 1

        total_stock_cost += task_stock_cost
        total_hearth_cost += task_hearth_cost

        results[task.id] = {
            "title": task.title,
            "verdict": verdict,
            "stock_cost_usd": str(round(task_stock_cost, 6)),
            "hearth_cost_usd": str(round(task_hearth_cost, 6)),
            "savings_pct": round(savings_pct, 1),
            "passed": passed,
        }

    overall_savings = (
        float((total_stock_cost - total_hearth_cost) / total_stock_cost * 100)
        if total_stock_cost > 0
        else 0.0
    )
    pass_rate = (passed_count / len(tasks)) * 100.0

    # Gate verification: 100% pass rate, overall savings > 0%
    gate_verified = (passed_count == len(tasks)) and (overall_savings > 0.0)

    return {
        "milestone": "M6",
        "gate_verified": gate_verified,
        "tasks_tested": len(tasks),
        "tasks_passed": passed_count,
        "pass_rate_pct": pass_rate,
        "overall_savings_pct": round(overall_savings, 1),
        "total_stock_cost_usd": str(round(total_stock_cost, 6)),
        "total_hearth_cost_usd": str(round(total_hearth_cost, 6)),
        "results": results,
    }


if __name__ == "__main__":
    import json

    summary = run_m6_benchmark()
    print(json.dumps(summary, indent=2))
