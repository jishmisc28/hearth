"""Dynamic wrapper proxy for LLM clients supporting observe and safe modes."""

from __future__ import annotations

import copy
import logging
import time
from collections.abc import Callable
from typing import Any

from hearth import HearthPrefixBreak
from hearth.adapters import (
    NormalizedUsage,
    parse_anthropic_usage,
    parse_gemini_usage,
    parse_openai_usage,
)
from hearth.cost import compute_call_cost
from hearth.guard import PrefixGuard
from hearth.layout import optimize_layout
from hearth.ledger import Ledger
from hearth.otel import record_span
from hearth.planner import get_ttl_optimizer, plan_breakpoints
from hearth.segments import segment_request
from hearth.sim.tokens import count_text_tokens
from hearth.trace import TraceRecorder, get_trace_recorder

logger = logging.getLogger(__name__)


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
            opt_system, opt_messages, layout_changes = optimize_layout(
                system=mod_kwargs.get("system", ""),
                messages=mod_kwargs.get("messages", []),
                tools=mod_kwargs.get("tools"),
            )
            if opt_system != mod_kwargs.get("system", ""):
                mod_kwargs["system"] = opt_system
            if opt_messages != mod_kwargs.get("messages", []):
                mod_kwargs["messages"] = opt_messages
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
        ts_first_token: float | None = None

        response = self._target_fn(*args, **send_kwargs)
        ts_end = time.time()

        model_name = str(kwargs.get("model", "unknown"))
        normalized_usage = self._extract_usage(response)

        # Compute cost in USD
        cost_info = compute_call_cost(
            provider=self.provider,
            model=model_name,
            read_tokens=normalized_usage.read,
            write_tokens=normalized_usage.write,
            uncached_tokens=normalized_usage.uncached,
            output_tokens=normalized_usage.output,
        )

        # Update SQLite summary ledger (INV-09: no content)
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

        # Record OpenTelemetry span if available (D-10)
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

        # Record JSONL trace
        body_to_record = None
        if self.record:
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

        return response

    def _extract_usage(self, response: Any) -> NormalizedUsage:
        """Normalize usage across providers into read, write, uncached, output (INV-06)."""
        if hasattr(response, "usage") and response.usage is not None:
            raw_u = response.usage
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
        mode: str = "observe",
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
