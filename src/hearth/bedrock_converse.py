"""Stdlib client for the Amazon Bedrock Converse API.

The API key is a bearer token and is never written to the ledger.
``session_id`` is a Hearth argument and is not sent.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from types import SimpleNamespace
from typing import Any

_BODY_KEYS = {"system", "messages", "inferenceConfig", "toolConfig"}


class BedrockConverse:
    """Posts to ``{endpoint}/model/{modelId}/converse``."""

    def __init__(self, endpoint: str, api_key: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self.last_payload: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> SimpleNamespace:
        model = str(kwargs.get("model", ""))
        if not model:
            raise RuntimeError("Bedrock Converse requires a model id")
        payload = {key: value for key, value in kwargs.items() if key in _BODY_KEYS}
        self.last_payload = payload
        url = f"{self._endpoint}/model/{model}/converse"
        request = urllib.request.Request(
            url,
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
            raise RuntimeError(f"Bedrock Converse HTTP {exc.code}: {detail}") from exc
        data = json.loads(raw)
        if "error" in data:
            raise RuntimeError(f"Bedrock Converse error: {data['error']}")
        usage = data.get("usage") or {}
        return SimpleNamespace(usage=usage, raw=data)
