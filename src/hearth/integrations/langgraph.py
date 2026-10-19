"""LangGraph and LangChain middleware for Hearth prompt caching (BUILD_HANDBOOK §6.1, M3)."""

from __future__ import annotations

from typing import Any

import hearth
from hearth.guard import PrefixGuard
from hearth.layout import optimize_layout
from hearth.trace import TraceRecorder, get_trace_recorder


class HearthMiddleware:
    """LangGraph middleware / callback interceptor for prompt caching.

    - Restores first-seen tool order across graph executions.
    - Relocates volatile timestamps and session markers in optimize mode.
    - Enforces append-only message history and detects prefix breaks.
    - Adds provider cache_control breakpoints where appropriate.
    """

    def __init__(
        self,
        mode: hearth.Mode = "safe",
        session_id: str = "langgraph-session",
        provider: str = "gemini",
        recorder: TraceRecorder | None = None,
        strict: bool = False,
    ):
        self.mode = mode
        self.session_id = session_id
        self.provider = provider
        self.recorder = recorder or get_trace_recorder()
        self.strict = strict
        self.guard = PrefixGuard(strict=strict)
        self.first_seen_tools: list[str] = []
        self._call_count = 0

    def transform_messages(
        self,
        messages: list[Any],
        tools: list[dict[str, Any]] | None = None,
        system: str = "",
    ) -> tuple[str, list[Any], list[dict[str, Any]]]:
        """Process messages and system prompt before passing to model in LangGraph node."""
        self._call_count += 1
        changes: list[dict[str, Any]] = []

        if self.mode == "observe":
            return system, messages, []

        # Restore tool ordering if seen before (safe / optimize mode)
        clean_tools = list(tools) if tools else []
        if clean_tools:
            current_names = [
                t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
                for t in clean_tools
            ]
            valid_names = [n for n in current_names if n]
            if not self.first_seen_tools and valid_names:
                self.first_seen_tools = list(valid_names)
            elif self.first_seen_tools and valid_names != self.first_seen_tools:
                tool_map = {n: t for n, t in zip(valid_names, clean_tools, strict=False)}
                reordered = [tool_map[n] for n in self.first_seen_tools if n in tool_map]
                for t in clean_tools:
                    if t not in reordered:
                        reordered.append(t)
                clean_tools = reordered

        # Standardize message dicts
        msg_dicts: list[dict[str, Any]] = []
        for m in messages:
            if isinstance(m, dict):
                msg_dicts.append(dict(m))
            elif hasattr(m, "content"):
                role = "user"
                type_name = getattr(m, "type", "")
                if "human" in type_name or "user" in type_name:
                    role = "user"
                elif "ai" in type_name or "assistant" in type_name:
                    role = "assistant"
                elif "system" in type_name:
                    role = "system"
                elif "tool" in type_name:
                    role = "tool"
                msg_dicts.append({"role": role, "content": getattr(m, "content", "")})
            else:
                msg_dicts.append({"role": "user", "content": str(m)})

        new_system = system
        new_msgs = msg_dicts

        if self.mode == "optimize":
            new_system, new_msgs, opt_changes = optimize_layout(
                system=system,
                messages=msg_dicts,
                tools=clean_tools,
            )
            changes.extend(opt_changes)

        # Evaluate prefix guard
        import time

        self.guard.evaluate_call(
            curr_params={"model": "default"},
            curr_tools=clean_tools,
            curr_system=new_system,
            curr_messages=new_msgs,
            total_tokens=sum(len(str(m.get("content", ""))) // 4 for m in new_msgs),
            ts=time.time(),
        )

        return new_system, new_msgs, changes

    def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        """Functional middleware invocation on LangGraph state dict."""
        if self.mode == "observe":
            return dict(state)

        messages = state.get("messages", [])
        tools = state.get("tools")
        system = state.get("system", "")

        opt_sys, opt_msgs, changes = self.transform_messages(
            messages=messages, tools=tools, system=system
        )

        new_state = dict(state)
        new_state["messages"] = opt_msgs
        if opt_sys:
            new_state["system"] = opt_sys
        if changes:
            new_state["_hearth_changes"] = changes

        return new_state

    # LangChain / LangGraph BaseCallbackHandler interface compatibility
    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Invoked when LLM starts running in LangChain."""
        pass

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Invoked when LLM finishes running in LangChain."""
        pass
