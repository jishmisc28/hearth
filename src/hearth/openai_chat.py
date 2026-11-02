"""Stdlib client for an OpenAI-compatible Chat Completions endpoint.

Bedrock's working path is ``/openai/v1/chat/completions``. The shorter
``/v1/chat/completions`` path on ``bedrock-runtime`` is not that operation.
The API key is sent as a bearer token and is never written to the ledger.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from types import SimpleNamespace
from typing import Any

_ALLOWED = {"model", "messages", "max_tokens", "temperature", "tools", "tool_choice"}


class ChatCompletions:
    """Object whose ``create`` method hearth.wrap can intercept."""

    def __init__(self, endpoint: str, api_key: str) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self.last_payload: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> SimpleNamespace:
        payload = {key: value for key, value in kwargs.items() if key in _ALLOWED}
        self.last_payload = payload
        request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise RuntimeError(f"chat completions HTTP {exc.code}: {detail}") from exc
        data = json.loads(raw)
        if "error" in data:
            raise RuntimeError(f"chat completions error: {data['error']}")
        usage = data.get("usage") or {}
        return SimpleNamespace(usage=usage, raw=data)


class _Chat:
    def __init__(self, completions: ChatCompletions) -> None:
        self.completions = completions


class OpenAIChatClient:
    """Minimal chat client. Pass the full completions URL as ``endpoint``."""

    def __init__(self, endpoint: str, api_key: str) -> None:
        self.chat = _Chat(ChatCompletions(endpoint, api_key))
