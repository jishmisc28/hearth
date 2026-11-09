"""Hearth arguments stay out of provider calls that do not accept them.

Gemini sends the prompt in ``contents``. The guard has to see that text.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hearth
from hearth.segments import contents_as_messages
from hearth.trace import TraceRecorder


def test_gemini_generate_content_does_not_receive_session_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))

    class Models:
        def __init__(self) -> None:
            self.kwargs: dict[str, Any] | None = None

        def generate_content(self, *, model: str, contents: str, config: Any = None) -> Any:
            self.kwargs = {"model": model, "contents": contents, "config": config}
            return SimpleNamespace(text="4")

    class Client:
        def __init__(self) -> None:
            self.models = Models()

    client = Client()
    wrapped = hearth.wrap(client, mode="safe")
    wrapped.models.generate_content(
        model="gemini-2.5-flash",
        contents="Hello",
        session_id="gem-1",
    )
    assert client.models.kwargs is not None
    assert client.models.kwargs["model"] == "gemini-2.5-flash"
    assert "session_id" not in client.models.kwargs
    assert "prompt_cache_key" not in client.models.kwargs


def test_openai_create_still_receives_prompt_cache_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))

    class ChatCompletions:
        def __init__(self) -> None:
            self.kwargs: dict[str, Any] | None = None

        def create(self, **kwargs: Any) -> SimpleNamespace:
            self.kwargs = kwargs
            return SimpleNamespace(usage={"prompt_tokens": 5, "completion_tokens": 1})

    class _Chat:
        def __init__(self) -> None:
            self.completions = ChatCompletions()

    class Client:
        def __init__(self) -> None:
            self.chat = _Chat()

    client = Client()
    wrapped = hearth.wrap(client, mode="safe")
    wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
        session_id="oa-1",
    )
    sent = client.chat.completions.kwargs
    assert sent is not None
    assert "session_id" not in sent
    assert sent.get("prompt_cache_key") == "hearth:oa-1"


def test_contents_parts_become_one_message() -> None:
    messages = contents_as_messages(
        [{"role": "user", "parts": [{"text": "Hello"}, {"text": "there"}]}]
    )
    assert messages == [{"role": "user", "content": "Hello\nthere"}]


def test_gemini_contents_mutation_is_not_counted_as_zero_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HEARTH_HOME", str(tmp_path))

    class Models:
        def __init__(self) -> None:
            self.seen: list[Any] = []

        def generate_content(self, *, model: str, contents: list[dict[str, Any]]) -> Any:
            self.seen.append(contents)
            return SimpleNamespace(text="4")

    class Client:
        def __init__(self) -> None:
            self.models = Models()

    # Same length the live Gemini check uses. The guard floor is 2,048 tokens.
    base = "This is a contract test knowledge base.\n" * 400
    contents = [{"role": "user", "parts": [{"text": f"Context: {base}\nQuestion: What is 2+2?"}]}]
    mutated = [
        {"role": "user", "parts": [{"text": f"Mutated Context: {base}\nQuestion: What is 2+2?"}]}
    ]
    recorder = TraceRecorder(trace_dir=tmp_path)
    client = Client()
    wrapped = hearth.wrap(client, mode="safe", recorder=recorder)
    wrapped.models.generate_content(
        model="gemini-2.5-flash", contents=contents, session_id="gem-contents"
    )
    wrapped.models.generate_content(
        model="gemini-2.5-flash", contents=contents, session_id="gem-contents"
    )
    wrapped.models.generate_content(
        model="gemini-2.5-flash", contents=mutated, session_id="gem-contents"
    )

    assert client.models.seen[0] == contents
    assert client.models.seen[2] == mutated
    trace = recorder.read_session("gem-contents")
    assert len(trace) == 3
    assert trace[0].get("breaks") == []
    assert trace[1].get("breaks") == []
    causes = [item.get("cause") for item in trace[2].get("breaks", [])]
    assert "below_minimum" not in causes
    assert "history_rewritten" in causes
