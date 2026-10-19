"""FakeProvider and test mock harness for Hearth prompt caching (BUILD_HANDBOOK §5.9, §11)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from hearth.sim.cache_sim import CacheSimulator


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class AnthropicUsage:
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class AnthropicResponse:
    id: str
    content: list[TextBlock]
    usage: AnthropicUsage
    type: str = "message"
    role: str = "assistant"


@dataclass
class OpenAIMessage:
    content: str
    role: str = "assistant"


@dataclass
class OpenAIChoice:
    message: OpenAIMessage
    index: int = 0


@dataclass
class OpenAIUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: dict[str, int]


@dataclass
class OpenAIResponse:
    id: str
    choices: list[OpenAIChoice]
    usage: OpenAIUsage


@dataclass
class GeminiPart:
    text: str


@dataclass
class GeminiContent:
    parts: list[GeminiPart]


@dataclass
class GeminiCandidate:
    content: GeminiContent


@dataclass
class GeminiUsageMetadata:
    prompt_token_count: int
    candidates_token_count: int
    cached_content_token_count: int
    total_token_count: int


@dataclass
class GeminiResponse:
    text: str
    candidates: list[GeminiCandidate]
    usage_metadata: GeminiUsageMetadata


class FakeMessagesEndpoint:
    """Mock for Anthropic client.messages endpoint."""

    def __init__(self, provider_parent: FakeProvider):
        self._parent = provider_parent

    def create(self, **kwargs: Any) -> AnthropicResponse:
        messages = kwargs.get("messages", [])
        system = kwargs.get("system", "")
        tools = kwargs.get("tools")
        ts = kwargs.get("ts", time.time())

        self._parent.call_count += 1
        sim_res = self._parent.simulator.simulate_call(
            call_index=self._parent.call_count,
            messages=messages,
            tools=tools,
            system=str(system) if system else None,
            ts=ts,
        )

        out_tokens = 50
        usage = AnthropicUsage(
            input_tokens=sim_res.total_input,
            output_tokens=out_tokens,
            cache_read_input_tokens=sim_res.predicted_read,
            cache_creation_input_tokens=sim_res.predicted_write,
        )

        return AnthropicResponse(
            id=f"fake-anthropic-msg-{self._parent.call_count}",
            content=[TextBlock(text="Fake simulated response from Anthropic model.")],
            usage=usage,
        )


class FakeCompletionsEndpoint:
    """Mock for OpenAI client.chat.completions endpoint."""

    def __init__(self, provider_parent: FakeProvider):
        self._parent = provider_parent

    def create(self, **kwargs: Any) -> OpenAIResponse:
        messages = kwargs.get("messages", [])
        tools = kwargs.get("tools")
        ts = kwargs.get("ts", time.time())

        self._parent.call_count += 1
        sim_res = self._parent.simulator.simulate_call(
            call_index=self._parent.call_count,
            messages=messages,
            tools=tools,
            system=None,
            ts=ts,
        )

        out_tokens = 45
        usage = OpenAIUsage(
            prompt_tokens=sim_res.total_input,
            completion_tokens=out_tokens,
            total_tokens=sim_res.total_input + out_tokens,
            prompt_tokens_details={"cached_tokens": sim_res.predicted_read},
        )

        return OpenAIResponse(
            id=f"fake-openai-chatcmpl-{self._parent.call_count}",
            choices=[
                OpenAIChoice(
                    message=OpenAIMessage(content="Fake simulated response from OpenAI model.")
                )
            ],
            usage=usage,
        )


class FakeChatEndpoint:
    def __init__(self, provider_parent: FakeProvider):
        self.completions = FakeCompletionsEndpoint(provider_parent)


class FakeModelsEndpoint:
    """Mock for Google GenAI client.models endpoint."""

    def __init__(self, provider_parent: FakeProvider):
        self._parent = provider_parent

    def generate_content(self, **kwargs: Any) -> GeminiResponse:
        contents = kwargs.get("contents", [])
        config = kwargs.get("config", {})
        system_instruction = config.get("system_instruction", "")
        tools = config.get("tools")
        ts = kwargs.get("ts", time.time())

        # Standardize contents into message list
        messages: list[dict[str, Any]] = []
        if isinstance(contents, list):
            for c in contents:
                if isinstance(c, dict):
                    messages.append(c)
                else:
                    messages.append({"role": "user", "content": str(c)})
        else:
            messages.append({"role": "user", "content": str(contents)})

        self._parent.call_count += 1
        sim_res = self._parent.simulator.simulate_call(
            call_index=self._parent.call_count,
            messages=messages,
            tools=tools,
            system=str(system_instruction) if system_instruction else None,
            ts=ts,
        )

        out_tokens = 60
        usage = GeminiUsageMetadata(
            prompt_token_count=sim_res.total_input,
            candidates_token_count=out_tokens,
            cached_content_token_count=sim_res.predicted_read,
            total_token_count=sim_res.total_input + out_tokens,
        )

        resp_text = "Fake simulated response from Gemini model."
        return GeminiResponse(
            text=resp_text,
            candidates=[GeminiCandidate(content=GeminiContent(parts=[GeminiPart(text=resp_text)]))],
            usage_metadata=usage,
        )


class FakeProvider:
    """Mock provider executing calls through the cache simulator without network requests (BUILD_HANDBOOK §5.9).

    Supports:
    - Anthropic: client.messages.create()
    - OpenAI: client.chat.completions.create()
    - Google Gemini: client.models.generate_content()
    """

    def __init__(self, provider: str = "gemini", model: str | None = None):
        self.provider = provider
        if model is None:
            if provider == "gemini":
                model = "gemini-2.5-flash"
            elif provider == "openai":
                model = "gpt-4o"
            else:
                model = "claude-3-5-sonnet"
        self.model = model
        self.simulator = CacheSimulator(provider=provider, model=model)
        self.call_count = 0

        # Endpoints
        self.messages = FakeMessagesEndpoint(self)
        self.chat = FakeChatEndpoint(self)
        self.models = FakeModelsEndpoint(self)

    def reset(self) -> None:
        self.call_count = 0
        self.simulator.reset()
