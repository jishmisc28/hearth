"""Four offline scenarios that show different cache outcomes.

These runs use the simulator and FakeProvider. They are not provider bills.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from hearth.replay import replay_trace_events

_STABLE = "You are a careful coding agent.\n" + ("Follow the repository rules. " * 800)
_TOOLS = [
    {"name": "read_file", "description": "Read a file"},
    {"name": "grep_search", "description": "Search the repo"},
    {"name": "run_tests", "description": "Run the test suite"},
]


@dataclass(frozen=True)
class ModeRow:
    mode: str
    read_pct: float
    cost_ratio: Decimal
    user_caused_breaks: int


@dataclass(frozen=True)
class Scenario:
    slug: str
    title: str
    story: str
    rows: tuple[ModeRow, ...]


def _call(
    ts: float,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "v": 1,
        "ts": ts,
        "request": {
            "kwargs": {
                "system": system,
                "messages": messages,
                "tools": tools if tools is not None else [],
            }
        },
    }


def clock_in_system() -> list[dict[str, Any]]:
    """A timestamp at the top of the system prompt, three turns."""
    calls = []
    messages: list[dict[str, Any]] = []
    for index, stamp in enumerate(
        ("2026-11-02T08:00:00", "2026-11-02T08:00:10", "2026-11-02T08:00:20")
    ):
        messages = [*messages, {"role": "user", "content": f"Turn {index + 1}"}]
        if index:
            messages = [
                *messages[:-1],
                {"role": "assistant", "content": "Noted."},
                messages[-1],
            ]
        calls.append(
            _call(
                ts=100.0 + index * 10,
                system=f"Current time: {stamp}\n{_STABLE}",
                messages=messages,
                tools=list(_TOOLS),
            )
        )
    return calls


def tools_shuffled() -> list[dict[str, Any]]:
    """The same tools come back in a different order on the second turn."""
    forward = list(_TOOLS)
    backward = list(reversed(_TOOLS))
    first = [{"role": "user", "content": "Find the bug."}]
    second = [
        {"role": "user", "content": "Find the bug."},
        {"role": "assistant", "content": "Looking."},
        {"role": "user", "content": "And fix the test."},
    ]
    return [
        _call(100.0, _STABLE, first, forward),
        _call(110.0, _STABLE, second, backward),
    ]


def too_short_to_cache() -> list[dict[str, Any]]:
    """One short question. The provider minimum is not met."""
    question = _call(100.0, "Be brief.", [{"role": "user", "content": "What is 2+2?"}])
    again = _call(110.0, "Be brief.", [{"role": "user", "content": "What is 2+2?"}])
    return [question, again]


def history_rewritten() -> list[dict[str, Any]]:
    """The first user message is edited on the next call."""
    return [
        _call(100.0, _STABLE, [{"role": "user", "content": "Original question."}], list(_TOOLS)),
        _call(
            110.0,
            _STABLE,
            [
                {"role": "user", "content": "A different question, rewritten in place."},
                {"role": "assistant", "content": "Noted."},
                {"role": "user", "content": "Continue."},
            ],
            list(_TOOLS),
        ),
    ]


def _rows(calls: list[dict[str, Any]]) -> tuple[ModeRow, ...]:
    rows: list[ModeRow] = []
    for mode in ("observe", "safe", "optimize"):
        summary = replay_trace_events(calls, mode=mode, provider="gemini", model="gemini-2.5-flash")
        rows.append(
            ModeRow(
                mode=mode,
                read_pct=summary.read_pct,
                cost_ratio=summary.cost_ratio,
                user_caused_breaks=summary.user_caused_breaks,
            )
        )
    return tuple(rows)


def run_scenarios() -> tuple[Scenario, ...]:
    """Replay the four scenarios. Prices come from the simulator."""
    return (
        Scenario(
            slug="clock",
            title="A clock at the top of the instructions",
            story=(
                "The system text is the same every turn except the time. "
                "Observe and safe send that changing line first, so nothing is read from cache "
                "and the guard blames the app. "
                "Optimize takes the time out of the instructions. "
                "On the next turn it writes the same time again onto the message it already sent, "
                "and puts the new time only on the new turn. "
                "The guard records no app-caused break. "
                "The input cost falls because the stable instructions are read from cache. "
                "The clock is a few tokens, so once those instructions are stable the read share barely moves."
            ),
            rows=_rows(clock_in_system()),
        ),
        Scenario(
            slug="tools",
            title="The same tools, in a new order",
            story=(
                "The second call sends the same three tools shuffled. "
                "Safe puts them back in the first-seen order before the simulator prices the call."
            ),
            rows=_rows(tools_shuffled()),
        ),
        Scenario(
            slug="short",
            title="Too short to cache",
            story=(
                "The prompt is one short question. "
                "A miss here is the provider minimum, and it is not counted as the application's fault."
            ),
            rows=_rows(too_short_to_cache()),
        ),
        Scenario(
            slug="rewrite",
            title="An earlier message was edited",
            story=(
                "The first user message changes on the next call. "
                "Hearth names that break. It does not quietly rewrite history to hide it."
            ),
            rows=_rows(history_rewritten()),
        ),
    )


def render_html(scenarios: tuple[Scenario, ...]) -> str:
    """A single page of the measured rows. No network, no invented numbers."""
    cards: list[str] = []
    for scenario in scenarios:
        body = []
        for row in scenario.rows:
            body.append(
                "<tr>"
                f"<td>{html.escape(row.mode)}</td>"
                f"<td>{row.read_pct:.1f}%</td>"
                f"<td>{row.cost_ratio:.2f}×</td>"
                f"<td>{row.user_caused_breaks}</td>"
                "</tr>"
            )
        cards.append(
            "<section>"
            f"<h2>{html.escape(scenario.title)}</h2>"
            f"<p>{html.escape(scenario.story)}</p>"
            "<table><thead><tr><th>Mode</th><th>Read share</th>"
            "<th>Input cost vs no cache</th><th>Breaks blamed on the app</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
            "</section>"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hearth scenarios</title>
<style>
  body {{ margin: 0; background: #f7f4ee; color: #1c1917;
    font-family: Palatino, Georgia, serif; font-size: 18px; line-height: 1.5; }}
  main {{ max-width: 760px; margin: 0 auto; padding: 40px 20px 72px; }}
  h1 {{ font-weight: 500; font-size: 36px; letter-spacing: -0.02em; margin: 0 0 8px; }}
  h2 {{ font-weight: 500; font-size: 24px; margin: 36px 0 8px; }}
  .kicker {{ font-family: "Avenir Next", "Segoe UI", sans-serif; font-size: 12px;
    letter-spacing: 0.12em; text-transform: uppercase; color: #9a3412; }}
  .note {{ background: #f8f1dc; border-left: 3px solid #854d0e; padding: 12px 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 16px; }}
  th, td {{ text-align: left; padding: 8px 8px 8px 0; border-bottom: 1px solid #e4ddd2; }}
  th {{ font-family: "Avenir Next", "Segoe UI", sans-serif; font-size: 12px;
    letter-spacing: 0.06em; text-transform: uppercase; color: #57534e; }}
</style>
</head>
<body>
<main>
  <p class="kicker">Hearth · four scenarios · simulator</p>
  <h1>The same library, four different outcomes</h1>
  <p class="note">These prices are the offline simulator for Gemini 2.5 Flash.
  They are not a provider bill. Regenerate this page with
  <code>hearth scenarios --html hearth-scenarios.html</code>.</p>
  {"".join(cards)}
</main>
</body>
</html>
"""


def write_html(path: str) -> tuple[Scenario, ...]:
    scenarios = run_scenarios()
    from pathlib import Path

    Path(path).write_text(render_html(scenarios), encoding="utf-8")
    return scenarios
