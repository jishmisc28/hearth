"""Dynamic wrapper proxy for LLM clients."""

from __future__ import annotations

import copy
import time
from collections.abc import Callable
from typing import Any

from hearth.trace import TraceRecorder, get_trace_recorder


class WrappedMethod:
    """Intercepts client creation calls to measure, protect, and trace prompt caching."""

    def __init__(
        self,
        target_fn: Callable[..., Any],
        provider: str,
        api: str,
        mode: str,
        record: bool,
        strict: bool,
        recorder: TraceRecorder | None = None,
    ):
        self._target_fn = target_fn
        self.provider = provider
        self.api = api
        self.mode = mode
        self.record = record
        self.strict = strict
        self.recorder = recorder or get_trace_recorder()
        self._call_counter = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self._call_counter += 1
        call_idx = self._call_counter

        # In observe mode: INV-01 requires sending byte-identical requests
        send_kwargs = kwargs
        if self.mode != "observe":
            send_kwargs = copy.deepcopy(kwargs)

        ts_start = time.time()
        ts_first_token: float | None = None

        response = self._target_fn(*args, **send_kwargs)
        ts_end = time.time()

        model_name = str(kwargs.get("model", "unknown"))
        normalized_usage = self._extract_usage(response)

        body_to_record = None
        if self.record:
            body_to_record = {
                "request": {
                    "args": [str(a) for a in args],
                    "kwargs": {k: v for k, v in kwargs.items() if k != "client"},
                },
                "response": self._extract_response_body(response),
            }

        session_id = kwargs.get("session_id", "default")
        self.recorder.record_call(
            session_id=session_id,
            call_index=call_idx,
            ts_start=ts_start,
            ts_end=ts_end,
            ts_first_token=ts_first_token,
            provider=self.provider,
            api=self.api,
            model=model_name,
            mode=self.mode,
            params={
                k: v
                for k, v in kwargs.items()
                if k in ("temperature", "top_p", "max_tokens", "stream")
            },
            fingerprints={"tools": [], "system": [], "messages": []},
            usage=normalized_usage,
            breaks=[],
            body=body_to_record,
            record_body=self.record,
        )

        return response

    def _extract_usage(self, response: Any) -> dict[str, Any]:
        """Normalize usage across providers into read, write, uncached, output."""
        read = 0
        write = 0
        uncached = 0
        output = 0
        raw: dict[str, Any] = {}

        if hasattr(response, "usage") and response.usage is not None:
            u = response.usage
            if hasattr(u, "model_dump"):
                raw = u.model_dump()
            elif isinstance(u, dict):
                raw = u
            else:
                raw = {k: getattr(u, k) for k in dir(u) if not k.startswith("_")}

            # Anthropic style
            if "cache_read_input_tokens" in raw or hasattr(u, "cache_read_input_tokens"):
                r_val = getattr(u, "cache_read_input_tokens", raw.get("cache_read_input_tokens", 0))
                w_val = getattr(
                    u, "cache_creation_input_tokens", raw.get("cache_creation_input_tokens", 0)
                )
                read = int(r_val or 0)
                write = int(w_val or 0)
                input_tot = int(getattr(u, "input_tokens", raw.get("input_tokens", 0)) or 0)
                output = int(getattr(u, "output_tokens", raw.get("output_tokens", 0)) or 0)
                uncached = max(0, input_tot - read - write)

            # OpenAI style
            elif "prompt_tokens" in raw or hasattr(u, "prompt_tokens"):
                input_tot = int(getattr(u, "prompt_tokens", raw.get("prompt_tokens", 0)) or 0)
                output = int(getattr(u, "completion_tokens", raw.get("completion_tokens", 0)) or 0)
                details = getattr(u, "prompt_tokens_details", raw.get("prompt_tokens_details", {}))
                if isinstance(details, dict):
                    read = int(details.get("cached_tokens", 0) or 0)
                elif hasattr(details, "cached_tokens"):
                    read = int(getattr(details, "cached_tokens", 0) or 0)
                write = int(getattr(u, "cache_write_tokens", raw.get("cache_write_tokens", 0)) or 0)
                uncached = max(0, input_tot - read - write)

        # Gemini style: usage_metadata
        elif hasattr(response, "usage_metadata") and response.usage_metadata is not None:
            um = response.usage_metadata
            read = int(getattr(um, "cached_content_token_count", 0) or 0)
            input_tot = int(getattr(um, "prompt_token_count", 0) or 0)
            output = int(getattr(um, "candidates_token_count", 0) or 0)
            uncached = max(0, input_tot - read)
            raw = {
                "prompt_token_count": input_tot,
                "cached_content_token_count": read,
                "candidates_token_count": output,
            }

        return {
            "raw": raw,
            "read": read,
            "write": write,
            "uncached": uncached,
            "output": output,
        }

    def _extract_response_body(self, response: Any) -> Any:
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if hasattr(response, "to_dict"):
            return response.to_dict()
        return str(response)


class WrappedClientProxy:
    """Proxy that wraps a provider client's create/generate methods."""

    def __init__(
        self,
        target_client: Any,
        mode: str = "observe",
        record: bool = False,
        strict: bool = False,
        recorder: TraceRecorder | None = None,
    ):
        self._target_client = target_client
        self.mode = mode
        self.record = record
        self.strict = strict
        self.recorder = recorder
        self._sub_proxies: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target_client, name)

        if name in ("messages", "chat", "models", "responses", "completions"):
            if name not in self._sub_proxies:
                self._sub_proxies[name] = WrappedClientProxy(
                    attr,
                    mode=self.mode,
                    record=self.record,
                    strict=self.strict,
                    recorder=self.recorder,
                )
            return self._sub_proxies[name]

        if name in ("create", "generate_content") and callable(attr):
            provider = "custom"
            api = name
            target_class_name = self._target_client.__class__.__name__.lower()
            if "anthropic" in target_class_name or "messages" in target_class_name:
                provider = "anthropic"
                api = "messages"
            elif "openai" in target_class_name or "chat" in target_class_name:
                provider = "openai"
                api = "chat"
            elif any(k in target_class_name for k in ("gemini", "models", "genai")):
                provider = "gemini"
                api = "generate_content"

            return WrappedMethod(
                attr,
                provider=provider,
                api=api,
                mode=self.mode,
                record=self.record,
                strict=self.strict,
                recorder=self.recorder,
            )

        return attr
