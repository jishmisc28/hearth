"""One live agent session per model that can cache.

Seven turns keep the same instructions and ask a new question.
The eighth turn changes the instructions, so the cache should miss.
Output is capped at 16 tokens. The run stops before the estimated bill reaches $1.

The API keys are read from the environment and are never printed.
"""

from __future__ import annotations

import json
import os
import tempfile
from decimal import Decimal
from typing import Any

import hearth
from hearth.adapters.gemini import parse_gemini_usage
from hearth.bedrock_converse import BedrockConverse, converse_endpoint
from hearth.cost import compute_call_cost

CAP = Decimal("1")
REPEATS = 1600
QUESTIONS = (
    "What is the stable rule in the instructions?",
    "Name one thing those instructions forbid.",
    "Do the instructions allow rewriting an earlier message?",
    "Where are provider prices stored?",
    "What is the default wrap mode?",
    "What should happen when Hearth itself throws?",
    "Which cache misses are never the caller's fault?",
)


def _corpus(prefix: str = "") -> str:
    body = "This is a contract test knowledge base.\n" * REPEATS
    return prefix + body


def _emit(row: dict[str, Any]) -> None:
    print(json.dumps(row, sort_keys=True), flush=True)


def _priced(provider: str, model: str, usage: dict[str, int]) -> Decimal | None:
    try:
        return compute_call_cost(
            provider=provider,
            model=model,
            read_tokens=usage["read"],
            write_tokens=usage["write"],
            uncached_tokens=usage["uncached"],
            output_tokens=usage["output"],
        ).actual_cost
    except KeyError:
        return None


def _usage_dict(read: int, write: int, uncached: int, output: int) -> dict[str, int]:
    return {"read": read, "write": write, "uncached": uncached, "output": output}


class _Spend:
    def __init__(self) -> None:
        self.spent = Decimal("0")

    def room(self, provider: str, model: str, tokens: int) -> bool:
        guess = _usage_dict(0, 0, tokens, 16)
        cost = _priced(provider, model, guess)
        reserve = cost if cost is not None else Decimal("0.05")
        if self.spent + reserve > CAP:
            _emit({"model": model, "stopped": "cap", "spent_usd": str(self.spent)})
            return False
        return True

    def add(self, provider: str, model: str, usage: dict[str, int]) -> str | None:
        cost = _priced(provider, model, usage)
        if cost is None:
            return None
        self.spent += cost
        return str(cost)


def _gemini_turn(wrapped: Any, model: str, text: str, question: str, session_id: str) -> Any:
    from google.genai import types

    contents = [
        {
            "role": "user",
            "parts": [{"text": f"{text}\nQuestion: {question}"}],
        }
    ]
    config = types.GenerateContentConfig(max_output_tokens=16, temperature=0.0)
    return wrapped.models.generate_content(
        model=model,
        contents=contents,
        config=config,
        session_id=session_id,
    )


def _gemini_usage(response: Any) -> dict[str, int]:
    parsed = parse_gemini_usage(getattr(response, "usage_metadata", None))
    return _usage_dict(parsed.read, parsed.write, parsed.uncached, parsed.output)


def _nova_turn(wrapped: Any, model: str, text: str, question: str, session_id: str) -> Any:
    system = [{"text": text}, {"cachePoint": {"type": "default"}}]
    messages = [{"role": "user", "content": [{"text": question}]}]
    return wrapped.create(
        model=model,
        system=system,
        messages=messages,
        inferenceConfig={"maxTokens": 16, "temperature": 0},
        session_id=session_id,
    )


def _nova_usage(response: Any) -> dict[str, int]:
    raw = response.usage if isinstance(response.usage, dict) else {}
    read = int(raw.get("cacheReadInputTokens") or 0)
    write = int(raw.get("cacheWriteInputTokens") or 0)
    uncached = int(raw.get("inputTokens") or 0)
    output = int(raw.get("outputTokens") or 0)
    return _usage_dict(read, write, uncached, output)


def _run_model(
    spend: _Spend,
    *,
    name: str,
    provider: str,
    model: str,
    call: Any,
    usage_of: Any,
) -> None:
    stable = _corpus()
    changed = _corpus("Changed rule. ")
    session_id = f"live-{name}"
    for index, question in enumerate(QUESTIONS, start=1):
        if not spend.room(provider, model, 20000):
            return
        try:
            response = call(model, stable, question, session_id)
            usage = usage_of(response)
        except Exception as exc:
            detail = str(exc)
            for secret_name in ("GEMINI_API_KEY", "BEDROCK_API_KEY"):
                secret = os.environ.get(secret_name, "")
                if secret:
                    detail = detail.replace(secret, "[redacted]")
            _emit(
                {
                    "case": "agent-session",
                    "model": model,
                    "turn": index,
                    "kind": "stable",
                    "error": detail[:400],
                }
            )
            return
        _emit(
            {
                "case": "agent-session",
                "model": model,
                "provider": provider,
                "turn": index,
                "kind": "stable",
                "usage": usage,
                "cost_usd": spend.add(provider, model, usage),
            }
        )
    if not spend.room(provider, model, 20000):
        return
    try:
        response = call(model, changed, "What changed in the instructions?", session_id)
        usage = usage_of(response)
    except Exception as exc:
        detail = str(exc)[:400]
        _emit(
            {
                "case": "agent-session",
                "model": model,
                "turn": len(QUESTIONS) + 1,
                "kind": "break",
                "error": detail,
            }
        )
        return
    _emit(
        {
            "case": "agent-session",
            "model": model,
            "provider": provider,
            "turn": len(QUESTIONS) + 1,
            "kind": "break",
            "usage": usage,
            "cost_usd": spend.add(provider, model, usage),
        }
    )


def _tool_spec(name: str, description: str) -> dict[str, Any]:
    return {
        "toolSpec": {
            "name": name,
            "description": description,
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                }
            },
        }
    }


def _nova_tools(changed: bool) -> list[dict[str, Any]]:
    search = (
        "Search the repository for a renamed symbol."
        if changed
        else "Search the repository for a symbol."
    )
    return [
        _tool_spec("search_repo", search),
        _tool_spec("read_file", "Read a file from the repository."),
        _tool_spec("run_tests", "Run the named test."),
    ]


def _assistant_blocks(response: Any) -> tuple[list[dict[str, Any]], str]:
    raw = getattr(response, "raw", None)
    if not isinstance(raw, dict):
        return [], ""
    blocks = raw.get("output", {}).get("message", {}).get("content")
    content = (
        [block for block in blocks if isinstance(block, dict)] if isinstance(blocks, list) else []
    )
    return content, str(raw.get("stopReason") or "")


def _tool_result_message(content: list[dict[str, Any]]) -> dict[str, Any] | None:
    results = []
    for block in content:
        if not isinstance(block, dict) or "toolUse" not in block:
            continue
        tool_use = block["toolUse"]
        results.append(
            {
                "toolResult": {
                    "toolUseId": str(tool_use.get("toolUseId") or "tool"),
                    "content": [{"text": "No matches."}],
                }
            }
        )
    if not results:
        return None
    return {"role": "user", "content": results}


def _run_nova_tools(spend: _Spend, wrapped: Any, model: str) -> None:
    """Stable instructions, a growing conversation, then one changed tool."""
    system_text = _corpus()
    session_id = f"tools-{model}"
    messages: list[dict[str, Any]] = []
    questions = (
        "Find where cache reads are counted.",
        "Open the price list loader.",
        "Run the cost test.",
        "Find the Nova model id.",
        "Read the live session runner.",
    )
    for index, question in enumerate(questions, start=1):
        if not spend.room("bedrock", model, 20000):
            return
        messages.append({"role": "user", "content": [{"text": question}]})
        try:
            response = wrapped.create(
                model=model,
                system=[{"text": system_text}, {"cachePoint": {"type": "default"}}],
                messages=messages,
                toolConfig={"tools": _nova_tools(False)},
                inferenceConfig={"maxTokens": 512, "temperature": 0},
                session_id=session_id,
            )
            usage = _nova_usage(response)
        except Exception as exc:
            detail = str(exc).replace(os.environ.get("BEDROCK_API_KEY", ""), "[redacted]")
            _emit(
                {
                    "case": "tool-session",
                    "model": model,
                    "provider": "bedrock",
                    "turn": index,
                    "kind": "stable",
                    "error": detail[:400],
                }
            )
            return
        content, stop = _assistant_blocks(response)
        _emit(
            {
                "case": "tool-session",
                "model": model,
                "provider": "bedrock",
                "turn": index,
                "kind": "stable",
                "stop": stop,
                "usage": usage,
                "cost_usd": spend.add("bedrock", model, usage),
            }
        )
        # A tool call cut off by the token cap is not a valid next message.
        # A finished tool call is followed by a short tool result.
        follow = _tool_result_message(content) if stop != "max_tokens" else None
        if follow is None:
            messages.append({"role": "assistant", "content": [{"text": "Noted."}]})
        else:
            messages.append({"role": "assistant", "content": content})
            messages.append(follow)
    if not spend.room("bedrock", model, 20000):
        return
    messages.append({"role": "user", "content": [{"text": "Search again with the updated tool."}]})
    try:
        response = wrapped.create(
            model=model,
            system=[{"text": system_text}, {"cachePoint": {"type": "default"}}],
            messages=messages,
            toolConfig={"tools": _nova_tools(True)},
            inferenceConfig={"maxTokens": 512, "temperature": 0},
            session_id=session_id,
        )
        usage = _nova_usage(response)
        _content, stop = _assistant_blocks(response)
    except Exception as exc:
        detail = str(exc).replace(os.environ.get("BEDROCK_API_KEY", ""), "[redacted]")
        _emit(
            {
                "case": "tool-session",
                "model": model,
                "provider": "bedrock",
                "turn": len(questions) + 1,
                "kind": "break",
                "error": detail[:400],
            }
        )
        return
    _emit(
        {
            "case": "tool-session",
            "model": model,
            "provider": "bedrock",
            "turn": len(questions) + 1,
            "kind": "break",
            "stop": stop,
            "usage": usage,
            "cost_usd": spend.add("bedrock", model, usage),
        }
    )


def main() -> None:
    os.environ["HEARTH_HOME"] = tempfile.mkdtemp(prefix="hearth-live-")
    spend = _Spend()
    if os.environ.get("LIVE_CASE") == "tools":
        if not os.environ.get("BEDROCK_API_KEY"):
            raise SystemExit("BEDROCK_API_KEY is not set")
        bedrock = BedrockConverse(
            converse_endpoint(os.environ.get("BEDROCK_ENDPOINT")),
            os.environ["BEDROCK_API_KEY"],
        )
        wrapped_bedrock = hearth.wrap(bedrock, mode="safe")
        for model in ("amazon.nova-micro-v1:0", "amazon.nova-lite-v1:0"):
            _run_nova_tools(spend, wrapped_bedrock, model)
        _emit({"case": "tool-session", "spent_usd": str(spend.spent), "cap_usd": "1"})
        return
    if os.environ.get("GEMINI_API_KEY"):
        from google import genai

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        wrapped = hearth.wrap(client, mode="safe")
        _run_model(
            spend,
            name="gemini",
            provider="gemini",
            model="gemini-2.5-flash",
            call=lambda model, text, question, session_id: _gemini_turn(
                wrapped, model, text, question, session_id
            ),
            usage_of=_gemini_usage,
        )
    else:
        _emit({"model": "gemini-2.5-flash", "skipped": "GEMINI_API_KEY is not set"})

    if os.environ.get("BEDROCK_API_KEY"):
        bedrock = BedrockConverse(
            converse_endpoint(os.environ.get("BEDROCK_ENDPOINT")),
            os.environ["BEDROCK_API_KEY"],
        )
        wrapped_bedrock = hearth.wrap(bedrock, mode="safe")
        for model in ("amazon.nova-micro-v1:0", "amazon.nova-lite-v1:0"):
            _run_model(
                spend,
                name=model,
                provider="bedrock",
                model=model,
                call=lambda model, text, question, session_id: _nova_turn(
                    wrapped_bedrock, model, text, question, session_id
                ),
                usage_of=_nova_usage,
            )
    else:
        _emit({"model": "bedrock", "skipped": "BEDROCK_API_KEY is not set"})

    _emit(
        {
            "skipped_models": [
                {
                    "model": "openai.gpt-oss-120b-1:0",
                    "reason": "No cache fields on the earlier calls, and the caching guide does not list it.",
                },
                {
                    "model": "claude-haiku",
                    "reason": "This account refused Haiku 5.5, retired the older Haiku ids, and blocked Haiku 4.5 after one call pending the Anthropic use-case form.",
                },
            ],
            "spent_usd": str(spend.spent),
            "cap_usd": "1",
        }
    )


if __name__ == "__main__":
    main()
