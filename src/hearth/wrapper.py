"""Dynamic wrapper proxy for LLM clients supporting observe and safe modes."""

from __future__ import annotations

import copy
import inspect
import logging
import time
from collections.abc import AsyncIterator, Callable, Iterator
from decimal import Decimal
from typing import Any

from hearth import HearthPrefixBreak
from hearth.adapters import (
    NormalizedUsage,
    parse_anthropic_usage,
    parse_bedrock_converse_usage,
    parse_gemini_usage,
    parse_openai_usage,
)
from hearth.cost import CallCost, compute_call_cost
from hearth.guard import PrefixGuard
from hearth.layout import (
    LayoutMemory,
    optimize_chat_messages,
    optimize_converse_system,
    optimize_layout,
)
from hearth.ledger import Ledger
from hearth.otel import record_span
from hearth.planner import get_ttl_optimizer, plan_breakpoints
from hearth.segments import segment_request
from hearth.sim.tokens import count_text_tokens
from hearth.trace import TraceRecorder, get_trace_recorder

logger = logging.getLogger(__name__)

# Arguments Hearth understands and the model API does not.
_HEARTH_ONLY = frozenset({"session_id"})


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
        ledger: Ledger | None = None,
    ):
        self._target_fn = target_fn
        self.provider = provider
        self.api = api
        self.mode = mode
        self.record = record
        self.strict = strict
        self.recorder = recorder or get_trace_recorder()
        self.ledger = ledger or Ledger()
        self.guard = PrefixGuard(strict=strict)
        self._layout_memory: dict[str, LayoutMemory] = {}
        self._call_counter = 0
        self._first_seen_tools_order: dict[str, list[dict[str, Any]]] = {}

    def _process_safe_request(
        self, kwargs: dict[str, Any], session_id: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        """Safe mode request processing:

        - Restores first-seen tool order if reordered (INV-02)
        - Preserves exact message and tool content
        - Adds cache planning metadata
        - Evaluates prefix guard divergence
        """
        mod_kwargs = copy.deepcopy(kwargs)
        breaks_list: list[dict[str, Any]] = []
        changes_list: list[dict[str, Any]] = []

        # 1. Restore first-seen tool order if application reordered them
        tools = mod_kwargs.get("tools")
        if tools and isinstance(tools, list):
            if session_id not in self._first_seen_tools_order:
                self._first_seen_tools_order[session_id] = list(tools)
            else:
                first_seen = self._first_seen_tools_order[session_id]
                first_seen_names = [str(t.get("name", "")) for t in first_seen]
                current_names = [str(t.get("name", "")) for t in tools]
                if (
                    sorted(first_seen_names) == sorted(current_names)
                    and first_seen_names != current_names
                ):
                    # Restore first-seen order!
                    tool_map = {str(t.get("name", "")): t for t in tools}
                    restored_tools = [
                        tool_map[name] for name in first_seen_names if name in tool_map
                    ]
                    mod_kwargs["tools"] = restored_tools
                    changes_list.append(
                        {
                            "kind": "tool_order_restored",
                            "first_seen_order": first_seen_names,
                            "reordered_order": current_names,
                            "details": "Restored first-seen tool order to protect prefix cache",
                        }
                    )
                    breaks_list.append(
                        {
                            "cause": "tools_reordered",
                            "user_caused": True,
                            "level": "tools",
                            "details": "Restored first-seen tool order in safe mode",
                        }
                    )

        # In optimize mode: optimize layout (relocate volatile system prompts, offload large tool outputs)
        if self.mode == "optimize":
            layout_memory = self._layout_memory.setdefault(session_id, LayoutMemory())
            raw_messages = mod_kwargs.get("messages")
            chat_messages: list[dict[str, Any]] | None = None
            if isinstance(raw_messages, list) and all(
                isinstance(item, dict) for item in raw_messages
            ):
                typed_messages: list[dict[str, Any]] = list(raw_messages)
                if any(message.get("role") == "system" for message in typed_messages):
                    chat_messages = typed_messages
            system_value = mod_kwargs.get("system", "")
            if isinstance(system_value, list):
                raw_for_converse = mod_kwargs.get("messages", [])
                converse_messages = raw_for_converse if isinstance(raw_for_converse, list) else []
                opt_system, opt_messages, layout_changes = optimize_converse_system(
                    system_value,
                    converse_messages,
                    tools=mod_kwargs.get("tools"),
                    memory=layout_memory,
                )
                if opt_system != system_value:
                    mod_kwargs["system"] = opt_system
                if opt_messages != converse_messages:
                    mod_kwargs["messages"] = opt_messages
                changes_list.extend(layout_changes)
            elif not mod_kwargs.get("system") and chat_messages is not None:
                opt_messages, layout_changes = optimize_chat_messages(
                    chat_messages,
                    tools=mod_kwargs.get("tools"),
                    memory=layout_memory,
                )
                if opt_messages != chat_messages:
                    mod_kwargs["messages"] = opt_messages
                changes_list.extend(layout_changes)
            else:
                system_text = system_value if isinstance(system_value, str) else ""
                layout_system, layout_messages, layout_changes = optimize_layout(
                    system=system_text,
                    messages=mod_kwargs.get("messages", []),
                    tools=mod_kwargs.get("tools"),
                    memory=layout_memory,
                )
                if layout_system != system_text:
                    mod_kwargs["system"] = layout_system
                if layout_messages != mod_kwargs.get("messages", []):
                    mod_kwargs["messages"] = layout_messages
                changes_list.extend(layout_changes)

        # 2. Segment request
        messages = mod_kwargs.get("messages", [])
        system = mod_kwargs.get("system", "")
        segments = segment_request(
            system=system,
            tools=mod_kwargs.get("tools"),
            messages=messages,
        )

        # 3. Guard divergence check (raises HearthPrefixBreak if strict=True)
        total_tokens = sum(count_text_tokens(str(s.data)) for s in segments)
        event = self.guard.evaluate_call(
            curr_params={k: v for k, v in kwargs.items() if k in ("model", "temperature")},
            curr_tools=mod_kwargs.get("tools", []),
            curr_system=str(system),
            curr_messages=messages,
            total_tokens=total_tokens,
            ts=time.time(),
        )
        if event is not None:
            breaks_list.append(
                {
                    "cause": event.cause,
                    "user_caused": event.user_caused,
                    "level": event.level,
                    "details": event.details,
                }
            )

        # 4. Plan breakpoints and TTL optimization (§5.4)
        from hearth import get_current_session

        curr_session = get_current_session()
        expected_calls = 2
        expected_pause = False
        if curr_session is not None:
            if curr_session._expected_calls is not None:
                expected_calls = curr_session._expected_calls
            expected_pause = curr_session._expected_pause

        get_ttl_optimizer().record_call(session_id)

        plan = plan_breakpoints(
            provider=self.provider,
            segments=segments,
            expected_calls=expected_calls,
            session_id=session_id,
            expected_pause=expected_pause,
        )
        if plan.should_cache and plan.prompt_cache_key:
            mod_kwargs["prompt_cache_key"] = plan.prompt_cache_key

        return mod_kwargs, breaks_list, changes_list

    def _outbound_kwargs(self, send_kwargs: dict[str, Any]) -> dict[str, Any]:
        """Drop Hearth-only arguments before the provider sees the call.

        ``prompt_cache_key`` is an OpenAI field. Gemini and Converse reject it.
        """
        cleaned = {key: value for key, value in send_kwargs.items() if key not in _HEARTH_ONLY}
        if self.provider != "openai":
            cleaned.pop("prompt_cache_key", None)
        return cleaned

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self._call_counter += 1
        call_idx = self._call_counter
        session_id = str(kwargs.get("session_id", "default"))

        send_kwargs = kwargs
        recorded_breaks: list[dict[str, Any]] = []
        recorded_changes: list[dict[str, Any]] = []

        if self.mode == "observe":
            # INV-01: observe sends byte-identical requests
            send_kwargs = kwargs
        elif self.mode in ("safe", "optimize"):
            try:
                send_kwargs, recorded_breaks, recorded_changes = self._process_safe_request(
                    kwargs, session_id
                )
            except HearthPrefixBreak:
                raise
            except Exception as e:
                # INV-07: Fail-open: internal error sends original request unchanged and records hearth_error
                logger.exception("Hearth internal error; failing open with original request: %s", e)
                send_kwargs = kwargs
                recorded_breaks.append(
                    {
                        "cause": "hearth_error",
                        "user_caused": False,
                        "level": "system",
                        "details": f"Internal Hearth exception: {e}",
                    }
                )

        ts_start = time.time()
        model_name = str(kwargs.get("model", "unknown"))
        response = self._target_fn(*args, **self._outbound_kwargs(send_kwargs))

        if inspect.isasyncgen(response):
            return self._wrap_async_stream(
                response,
                args=args,
                kwargs=kwargs,
                session_id=session_id,
                call_idx=call_idx,
                model_name=model_name,
                ts_start=ts_start,
                recorded_breaks=recorded_breaks,
                recorded_changes=recorded_changes,
            )
        if inspect.iscoroutine(response):
            return self._wrap_coroutine(
                response,
                args=args,
                kwargs=kwargs,
                session_id=session_id,
                call_idx=call_idx,
                model_name=model_name,
                ts_start=ts_start,
                recorded_breaks=recorded_breaks,
                recorded_changes=recorded_changes,
            )
        if self._is_sync_stream(response, kwargs.get("stream")):
            return self._wrap_sync_stream(
                response,
                args=args,
                kwargs=kwargs,
                session_id=session_id,
                call_idx=call_idx,
                model_name=model_name,
                ts_start=ts_start,
                recorded_breaks=recorded_breaks,
                recorded_changes=recorded_changes,
            )

        self._finalize_call(
            response,
            args=args,
            kwargs=kwargs,
            session_id=session_id,
            call_idx=call_idx,
            model_name=model_name,
            ts_start=ts_start,
            ts_end=time.time(),
            ts_first_token=None,
            recorded_breaks=recorded_breaks,
            recorded_changes=recorded_changes,
        )
        return response

    def _is_sync_stream(self, response: Any, stream_flag: Any) -> bool:
        if not stream_flag or isinstance(response, (str, bytes, dict, list)):
            return False
        return isinstance(response, Iterator)

    def _finalize_call(
        self,
        response: Any,
        *,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        session_id: str,
        call_idx: int,
        model_name: str,
        ts_start: float,
        ts_end: float,
        ts_first_token: float | None,
        recorded_breaks: list[dict[str, Any]],
        recorded_changes: list[dict[str, Any]],
    ) -> None:
        normalized_usage = (
            self._extract_usage(response)
            if response is not None
            else NormalizedUsage(read=0, write=0, uncached=0, output=0, total_input=0, raw={})
        )
        try:
            cost_info = compute_call_cost(
                provider=self.provider,
                model=model_name,
                read_tokens=normalized_usage.read,
                write_tokens=normalized_usage.write,
                uncached_tokens=normalized_usage.uncached,
                output_tokens=normalized_usage.output,
            )
        except KeyError as exc:
            logger.warning("No sourced price for %s/%s", self.provider, model_name)
            cost_info = CallCost(
                actual_cost=Decimal("0"),
                uncached_baseline=Decimal("0"),
                savings_amount=Decimal("0"),
                cost_ratio=Decimal("1"),
            )
            recorded_breaks.append(
                {
                    "cause": "hearth_error",
                    "user_caused": False,
                    "level": "system",
                    "details": f"No sourced price in providers.toml: {exc}",
                }
            )

        prefix_was_stable = not any(
            item.get("cause") not in ("hearth_error",) for item in recorded_breaks
        )
        if (
            self.mode in ("safe", "optimize")
            and call_idx > 1
            and prefix_was_stable
            and normalized_usage.read == 0
            and normalized_usage.total_input >= self.guard.min_prefix_tokens
        ):
            recorded_breaks.append(
                {
                    "cause": "provider_miss",
                    "user_caused": False,
                    "level": "system",
                    "details": "Identical prefix had 0 cached tokens reported by the provider",
                }
            )

        self.ledger.record_call(
            session_id=session_id,
            call_index=call_idx,
            ts_start=ts_start,
            ts_end=ts_end,
            provider=self.provider,
            model=model_name,
            mode=self.mode,
            read_tokens=normalized_usage.read,
            write_tokens=normalized_usage.write,
            uncached_tokens=normalized_usage.uncached,
            output_tokens=normalized_usage.output,
            cost_usd=cost_info.actual_cost,
            breaks_count=len(recorded_breaks),
        )
        record_span(
            session_id=session_id,
            call_index=call_idx,
            provider=self.provider,
            model=model_name,
            mode=self.mode,
            read_tokens=normalized_usage.read,
            write_tokens=normalized_usage.write,
            uncached_tokens=normalized_usage.uncached,
            output_tokens=normalized_usage.output,
            cost_usd=str(cost_info.actual_cost),
            breaks_count=len(recorded_breaks),
        )
        body_to_record = None
        if self.record and response is not None:
            body_to_record = {
                "request": {
                    "args": [str(a) for a in args],
                    "kwargs": {k: v for k, v in kwargs.items() if k != "client"},
                },
                "response": self._extract_response_body(response),
            }
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
            usage={
                "raw": normalized_usage.raw,
                "read": normalized_usage.read,
                "write": normalized_usage.write,
                "uncached": normalized_usage.uncached,
                "output": normalized_usage.output,
                "cost_usd": str(cost_info.actual_cost),
            },
            breaks=recorded_breaks,
            changes=recorded_changes,
            body=body_to_record,
            record_body=self.record,
        )

    def _wrap_sync_stream(
        self,
        response: Iterator[Any],
        **finish: Any,
    ) -> Iterator[Any]:
        def chunks() -> Iterator[Any]:
            first_at: float | None = None
            last: Any = None
            try:
                for item in response:
                    if first_at is None:
                        first_at = time.time()
                    last = item
                    yield item
            finally:
                self._finalize_quietly(last, ts_first_token=first_at, **finish)

        return chunks()

    def _wrap_coroutine(self, response: Any, **finish: Any) -> Any:
        async def awaited() -> Any:
            inner = await response
            self._finalize_quietly(inner, ts_first_token=None, ts_end=time.time(), **finish)
            return inner

        return awaited()

    def _wrap_async_stream(self, response: AsyncIterator[Any], **finish: Any) -> AsyncIterator[Any]:
        async def chunks() -> AsyncIterator[Any]:
            first_at: float | None = None
            last: Any = None
            try:
                async for item in response:
                    if first_at is None:
                        first_at = time.time()
                    last = item
                    yield item
            finally:
                self._finalize_quietly(last, ts_first_token=first_at, **finish)

        return chunks()

    def _finalize_quietly(self, response: Any, **finish: Any) -> None:
        try:
            self._finalize_call(
                response,
                ts_end=finish.pop("ts_end", time.time()),
                **finish,
            )
        except Exception:
            logger.exception("Hearth could not record a finished call")

    def _extract_usage(self, response: Any) -> NormalizedUsage:
        """Normalize usage across providers into read, write, uncached, output (INV-06)."""
        if hasattr(response, "usage") and response.usage is not None:
            raw_u = response.usage
            if self.provider == "bedrock" or (
                isinstance(raw_u, dict) and "cacheReadInputTokens" in raw_u
            ):
                return parse_bedrock_converse_usage(raw_u)
            if self.provider == "anthropic" or (
                isinstance(raw_u, dict) and "cache_read_input_tokens" in raw_u
            ):
                return parse_anthropic_usage(raw_u)
            return parse_openai_usage(raw_u)

        if hasattr(response, "usage_metadata") and response.usage_metadata is not None:
            return parse_gemini_usage(response.usage_metadata)

        # Default fallback: zero usage
        return NormalizedUsage(read=0, write=0, uncached=0, output=0, total_input=0, raw={})

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
        mode: str = "safe",
        record: bool = False,
        strict: bool = False,
        recorder: TraceRecorder | None = None,
        ledger: Ledger | None = None,
    ):
        self._target_client = target_client
        self.mode = mode
        self.record = record
        self.strict = strict
        self.recorder = recorder
        self.ledger = ledger
        self._sub_proxies: dict[str, Any] = {}
        self._wrapped_methods: dict[str, WrappedMethod] = {}

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
                    ledger=self.ledger,
                )
            return self._sub_proxies[name]

        if name in ("create", "generate_content") and callable(attr):
            if name not in self._wrapped_methods:
                provider = "gemini"
                api = name
                target_class_name = self._target_client.__class__.__name__.lower()
                if "anthropic" in target_class_name or "messages" in target_class_name:
                    provider = "anthropic"
                    api = "messages"
                elif "bedrock" in target_class_name:
                    provider = "bedrock"
                    api = "converse"
                elif "openai" in target_class_name or "chat" in target_class_name:
                    provider = "openai"
                    api = "chat"
                elif any(k in target_class_name for k in ("gemini", "models", "genai")):
                    provider = "gemini"
                    api = "generate_content"

                self._wrapped_methods[name] = WrappedMethod(
                    attr,
                    provider=provider,
                    api=api,
                    mode=self.mode,
                    record=self.record,
                    strict=self.strict,
                    recorder=self.recorder,
                    ledger=self.ledger,
                )

            return self._wrapped_methods[name]

        return attr
