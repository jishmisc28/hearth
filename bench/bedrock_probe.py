"""One manual Bedrock check. Stops before the estimated bill reaches $1.

Nova Micro and Nova Lite have sourced prices. A Claude Haiku id is tried
until one answers; its tokens are recorded, and its dollars are not invented.
gpt-oss is not called. The earlier run returned no cache fields.

The API key is read from the environment and is never printed.
"""

from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal
from typing import Any

import hearth
from hearth.bedrock_converse import BedrockConverse, converse_endpoint
from hearth.cost import compute_call_cost

CAP = Decimal("1")
# Used only to refuse another call when a model has no sourced price.
# This is not a price and is not a saving.
UNPRICED_INPUT_PER_MILLION = Decimal("20")
UNPRICED_OUTPUT_PER_MILLION = Decimal("80")

NOVA_MODELS = (
    "amazon.nova-micro-v1:0",
    "amazon.nova-lite-v1:0",
)
CLAUDE_CANDIDATES = (
    "us.anthropic.claude-haiku-5-5",
    "anthropic.claude-haiku-5-5",
    "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "anthropic.claude-3-5-haiku-20241022-v1:0",
    "us.anthropic.claude-3-haiku-20240307-v1:0",
)
# Haiku 4.5's cache minimum is 4,096 tokens, so it gets a longer prompt.
HAIKU_45 = (
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "anthropic.claude-haiku-4-5-20251001-v1:0",
)


def _prompt(repeats: int = 140) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = "The repository rule is stable. " * repeats
    system = [{"text": text}, {"cachePoint": {"type": "default"}}]
    messages = [{"role": "user", "content": [{"text": "Reply with the single word ok."}]}]
    return system, messages


def _priced(model: str, usage: dict[str, int]) -> Decimal | None:
    try:
        cost = compute_call_cost(
            provider="bedrock",
            model=model,
            read_tokens=usage["read"],
            write_tokens=usage["write"],
            uncached_tokens=usage["uncached"],
            output_tokens=usage["output"],
        )
    except KeyError:
        return None
    return cost.actual_cost


def _ceiling(usage: dict[str, int]) -> Decimal:
    million = Decimal("1000000")
    incoming = Decimal(usage["read"] + usage["write"] + usage["uncached"])
    outgoing = Decimal(usage["output"])
    return (UNPRICED_INPUT_PER_MILLION * incoming / million) + (
        UNPRICED_OUTPUT_PER_MILLION * outgoing / million
    )


def _usage(raw: Any) -> dict[str, int]:
    data = raw if isinstance(raw, dict) else {}
    return {
        "read": int(data.get("cacheReadInputTokens") or 0),
        "write": int(data.get("cacheWriteInputTokens") or 0),
        "uncached": int(data.get("inputTokens") or 0),
        "output": int(data.get("outputTokens") or 0),
    }


def _emit(row: dict[str, Any]) -> None:
    print(json.dumps(row, sort_keys=True), flush=True)


def main() -> None:
    api_key = os.environ.get("BEDROCK_API_KEY", "")
    if not api_key:
        raise SystemExit("BEDROCK_API_KEY is not set")
    os.environ["HEARTH_HOME"] = tempfile.mkdtemp(prefix="hearth-probe-")
    endpoint = converse_endpoint(os.environ.get("BEDROCK_ENDPOINT"))
    client = BedrockConverse(endpoint, api_key)
    wrapped = hearth.wrap(client, mode="safe")
    short_system, short_messages = _prompt(140)
    long_system, long_messages = _prompt(650)
    limits = {"maxTokens": 8, "temperature": 0}
    only = os.environ.get("PROBE_ONLY", "").strip()
    spent = Decimal("0")

    _emit(
        {
            "skipped": "openai.gpt-oss-120b-1:0",
            "reason": "Earlier calls returned no cache fields, and the Bedrock caching guide does not list gpt-oss.",
        }
    )

    def room_for(model: str, tokens: int = 2000) -> bool:
        guess = {"read": 0, "write": tokens, "uncached": 0, "output": 8}
        reserve = _priced(model, guess)
        if reserve is None:
            reserve = _ceiling(guess)
        if spent + reserve > CAP:
            _emit({"model": model, "stopped": "cap", "spent_usd": str(spent)})
            return False
        return True

    def one_call(
        model: str,
        label: str,
        system: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tokens: int,
    ) -> dict[str, Any] | None:
        nonlocal spent
        if not room_for(model, tokens):
            return None
        try:
            response = wrapped.create(
                model=model,
                system=system,
                messages=messages,
                inferenceConfig=limits,
                session_id=f"probe-{model}",
            )
        except RuntimeError as exc:
            detail = str(exc).replace(api_key, "[redacted]")
            _emit({"model": model, "label": label, "error": detail[:400]})
            return {"error": detail}
        usage = _usage(response.usage)
        cost = _priced(model, usage)
        if cost is None:
            spent += _ceiling(usage)
            shown = None
        else:
            spent += cost
            shown = str(cost)
        _emit({"model": model, "label": label, "usage": usage, "cost_usd": shown})
        return {"usage": usage}

    nova_models = () if only else NOVA_MODELS
    claude_models = (only,) if only else CLAUDE_CANDIDATES
    for model in nova_models:
        first = one_call(model, "write", short_system, short_messages, 2000)
        if first is None or "error" in first:
            continue
        one_call(model, "read", short_system, short_messages, 2000)

    claude_hit = False
    for model in claude_models:
        prompt_system, prompt_messages, tokens = short_system, short_messages, 2000
        if "haiku-4-5" in model:
            prompt_system, prompt_messages, tokens = long_system, long_messages, 8000
        first = one_call(model, "write", prompt_system, prompt_messages, tokens)
        if first is None:
            break
        if "error" in first:
            continue
        second = one_call(model, "read", prompt_system, prompt_messages, tokens)
        if second is not None:
            claude_hit = True
            break

    if not only and not claude_hit:
        for model in HAIKU_45:
            first = one_call(model, "write", long_system, long_messages, 8000)
            if first is None:
                break
            if "error" in first:
                continue
            second = one_call(model, "read", long_system, long_messages, 8000)
            if second is not None:
                break

    _emit({"spent_usd_priced_plus_ceiling": str(spent), "cap_usd": "1"})


if __name__ == "__main__":
    main()
