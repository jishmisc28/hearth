"""Broader live session. Stops before the estimated bill reaches $5.

Kimi K3, Grok, and Nova Pro have cache prices in the 2026-11-11 US East list,
so they get a full session. Claude and the newer OpenAI ids are not in that
list, so each gets one short call and no long prompt. There is no direct
OpenAI key in this repo.

The API keys are read from the environment and are never printed.
"""

from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any

import hearth
from hearth.bedrock_converse import BedrockConverse, converse_endpoint
from hearth.cost import compute_call_cost

CAP = Decimal("5")
LINE = "This is a contract test knowledge base.\n"
CHAT_HOST = "https://bedrock-runtime.us-east-1.amazonaws.com"
QUESTIONS = (
    "What is the stable rule in the instructions?",
    "Name one thing those instructions forbid.",
    "Do the instructions allow rewriting an earlier message?",
    "Where are provider prices stored?",
    "What is the default wrap mode?",
    "What should happen when Hearth itself throws?",
)
CLAUDE_PROBES = (
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.anthropic.claude-haiku-5-5",
    "us.anthropic.claude-sonnet-4-6",
)
OPENAI_PROBES = (
    "openai.gpt-5.4",
    "openai.gpt-5.5",
    "openai.gpt-5.6-luna",
)
KIMI_IDS = ("us.moonshotai.kimi-k3", "moonshotai.kimi-k3")
GROK_IDS = ("us.xai.grok-4.7", "xai.grok-4.7", "us.xai.grok-4.6", "xai.grok-4.6")


def _emit(row: dict[str, Any]) -> None:
    print(json.dumps(row, sort_keys=True), flush=True)


def parse_usage(usage: dict[str, Any]) -> dict[str, int] | None:
    """Split a provider usage object into read, write, and the uncached tail.

    Returns None when the fields do not add up to the provider's input total.
    """
    if "cacheReadInputTokens" in usage or "cacheReadInputTokenCount" in usage:
        read = int(usage.get("cacheReadInputTokens") or usage.get("cacheReadInputTokenCount") or 0)
        write = int(
            usage.get("cacheWriteInputTokens") or usage.get("cacheWriteInputTokenCount") or 0
        )
        tail = int(usage.get("inputTokens") or 0)
        output = int(usage.get("outputTokens") or 0)
        return {"read": read, "write": write, "uncached": tail, "output": output}
    prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
    if prompt is None:
        return None
    details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
    if not isinstance(details, dict):
        details = {}
    read = int(details.get("cached_tokens") or usage.get("cached_tokens") or 0)
    write = int(
        details.get("cache_write_tokens")
        or usage.get("cache_write_tokens")
        or usage.get("cache_write_input_tokens")
        or 0
    )
    output = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    uncached = int(prompt) - read - write
    if uncached < 0:
        return None
    return {"read": read, "write": write, "uncached": uncached, "output": output}


def _priced(model: str, usage: dict[str, int]) -> Decimal | None:
    try:
        return compute_call_cost(
            provider="bedrock",
            model=model,
            read_tokens=usage["read"],
            write_tokens=usage["write"],
            uncached_tokens=usage["uncached"],
            output_tokens=usage["output"],
        ).actual_cost
    except KeyError:
        return None


class _Spend:
    def __init__(self) -> None:
        self.priced = Decimal("0")
        self.unknown = Decimal("0")

    def room(self, model: str, tokens: int, *, as_write: bool = False) -> bool:
        if as_write:
            guess = {"read": 0, "write": tokens, "uncached": 0, "output": 32}
        else:
            guess = {"read": 0, "write": 0, "uncached": tokens, "output": 32}
        cost = _priced(model, guess)
        reserve = cost if cost is not None else Decimal("0.05")
        if self.priced + self.unknown + reserve > CAP:
            _emit(
                {
                    "model": model,
                    "stopped": "cap",
                    "spent_usd": str(self.priced),
                    "unknown_reserve_usd": str(self.unknown),
                }
            )
            return False
        return True

    def add(self, model: str, usage: dict[str, int]) -> str | None:
        cost = _priced(model, usage)
        if cost is None:
            self.unknown += Decimal("0.05")
            return None
        self.priced += cost
        return str(cost)


def _redact(detail: str) -> str:
    key = os.environ.get("BEDROCK_API_KEY", "")
    if key:
        detail = detail.replace(key, "[redacted]")
    return detail[:400]


def _post(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    key = os.environ["BEDROCK_API_KEY"]
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {_redact(detail)}") from exc
    if isinstance(body, dict) and body.get("error"):
        raise RuntimeError(f"error: {_redact(str(body['error']))}")
    return body if isinstance(body, dict) else {}


def _chat(model: str, system_text: str, question: str, timeout: int = 180) -> dict[str, Any]:
    payload = {
        "model": model,
        "max_tokens": 32,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system_text,
                        "prompt_cache_breakpoint": {"mode": "explicit"},
                    }
                ],
            },
            {"role": "user", "content": question},
        ],
        "prompt_cache_options": {"mode": "explicit"},
    }
    return _post(f"{CHAT_HOST}/openai/v1/chat/completions", payload, timeout)


def _record(model: str, turn: int, kind: str, body: dict[str, Any], spend: _Spend) -> bool:
    usage_raw = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    parsed = parse_usage(usage_raw)
    if parsed is None:
        _emit(
            {
                "case": "broad",
                "model": model,
                "turn": turn,
                "kind": kind,
                "error": "usage did not reconcile",
                "raw_usage": usage_raw,
            }
        )
        spend.unknown += Decimal("0.05")
        return False
    _emit(
        {
            "case": "broad",
            "model": model,
            "provider": "bedrock",
            "turn": turn,
            "kind": kind,
            "usage": parsed,
            "raw_usage": usage_raw,
            "cost_usd": spend.add(model, parsed),
        }
    )
    return True


def _fail(model: str, turn: int, kind: str, exc: Exception) -> None:
    _emit(
        {
            "case": "broad",
            "model": model,
            "turn": turn,
            "kind": kind,
            "error": _redact(str(exc)),
        }
    )


def _first_chat(spend: _Spend, ids: tuple[str, ...], text: str) -> str | None:
    for model in ids:
        if not spend.room(model, 64, as_write=True):
            return None
        try:
            body = _chat(model, text, "Reply with ok.", timeout=60)
        except Exception as exc:
            _fail(model, 0, "probe", exc)
            message = str(exc)
            if "use case" in message.lower():
                return None
            continue
        if _record(model, 0, "probe", body, spend):
            return model
    return None


def _chat_session(spend: _Spend, model: str, reps: int) -> None:
    system = LINE * reps
    calls = [(question, "stable", system) for question in QUESTIONS]
    calls.append(("What changed?", "break", "Changed rule. " + system))
    for index, (question, kind, text) in enumerate(calls, start=1):
        if not spend.room(model, reps * 10, as_write=True):
            return
        try:
            body = _chat(model, text, question)
        except Exception as exc:
            _fail(model, index, kind, exc)
            return
        if not _record(model, index, kind, body, spend):
            return


def _nova_pro(spend: _Spend, wrapped: Any) -> None:
    model = "amazon.nova-pro-v1:0"
    system = LINE * 1800
    for index, question in enumerate(QUESTIONS, start=1):
        if not spend.room(model, 16000):
            return
        try:
            response = wrapped.create(
                model=model,
                system=[{"text": system}, {"cachePoint": {"type": "default"}}],
                messages=[{"role": "user", "content": [{"text": question}]}],
                inferenceConfig={"maxTokens": 16, "temperature": 0},
                session_id="broad-nova-pro",
            )
        except Exception as exc:
            _fail(model, index, "stable", exc)
            return
        usage = getattr(response, "usage", {}) or {}
        if not _record(model, index, "stable", {"usage": usage}, spend):
            return
    if not spend.room(model, 16000):
        return
    try:
        response = wrapped.create(
            model=model,
            system=[{"text": "Changed rule. " + system}, {"cachePoint": {"type": "default"}}],
            messages=[{"role": "user", "content": [{"text": "What changed?"}]}],
            inferenceConfig={"maxTokens": 16, "temperature": 0},
            session_id="broad-nova-pro",
        )
    except Exception as exc:
        _fail(model, len(QUESTIONS) + 1, "break", exc)
        return
    usage = getattr(response, "usage", {}) or {}
    _record(model, len(QUESTIONS) + 1, "break", {"usage": usage}, spend)


def _claude_probe(spend: _Spend, wrapped: Any) -> None:
    for model in CLAUDE_PROBES:
        if not spend.room(model, 64):
            return
        try:
            response = wrapped.create(
                model=model,
                system=[{"text": "Reply briefly."}, {"cachePoint": {"type": "default"}}],
                messages=[{"role": "user", "content": [{"text": "Say ok."}]}],
                inferenceConfig={"maxTokens": 8, "temperature": 0},
                session_id="broad-claude",
            )
        except Exception as exc:
            _fail(model, 0, "probe", exc)
            if "use case" in str(exc).lower():
                return
            continue
        usage = getattr(response, "usage", {}) or {}
        _record(model, 0, "probe", {"usage": usage}, spend)
        _emit({"model": model, "skipped_long_session": "no price row in the 2026-11-11 list"})
        return


def _openai_probe(spend: _Spend) -> None:
    for model in OPENAI_PROBES:
        if not spend.room(model, 32):
            return
        try:
            body = _post(
                f"{CHAT_HOST}/openai/v1/chat/completions",
                {
                    "model": model,
                    "max_tokens": 8,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": "Say ok."}],
                },
                60,
            )
        except Exception as exc:
            _fail(model, 0, "probe", exc)
            continue
        _record(model, 0, "probe", body, spend)
        _emit({"model": model, "skipped_long_session": "no price row in the 2026-11-11 list"})
        return


def main() -> None:
    os.environ["HEARTH_HOME"] = tempfile.mkdtemp(prefix="hearth-broad-")
    if not os.environ.get("BEDROCK_API_KEY"):
        raise SystemExit("BEDROCK_API_KEY is not set")
    spend = _Spend()
    _emit({"case": "broad", "cap_usd": "5", "direct_openai": "no OPENAI_API_KEY"})
    converse = BedrockConverse(
        converse_endpoint(os.environ.get("BEDROCK_ENDPOINT")),
        os.environ["BEDROCK_API_KEY"],
    )
    wrapped = hearth.wrap(converse, mode="safe")
    _claude_probe(spend, wrapped)
    _openai_probe(spend)
    kimi = _first_chat(spend, KIMI_IDS, "Reply briefly.")
    if kimi is not None:
        _chat_session(spend, kimi, 12000)
    grok = _first_chat(spend, GROK_IDS, "Reply briefly.")
    if grok is not None:
        _chat_session(spend, grok, 8000)
    _nova_pro(spend, wrapped)
    _emit(
        {
            "case": "broad",
            "spent_usd": str(spend.priced),
            "unknown_reserve_usd": str(spend.unknown),
            "cap_usd": "5",
        }
    )


if __name__ == "__main__":
    main()
