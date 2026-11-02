"""The four offline scenarios must not collapse into one result."""

from __future__ import annotations

from hearth.scenarios import Scenario, run_scenarios


def _by_slug() -> dict[str, Scenario]:
    return {scenario.slug: scenario for scenario in run_scenarios()}


def test_clock_optimize_reads_more_than_observe() -> None:
    rows = {row.mode: row for row in _by_slug()["clock"].rows}
    assert rows["optimize"].read_pct > rows["observe"].read_pct
    assert rows["optimize"].cost_ratio < rows["observe"].cost_ratio


def test_shuffled_tools_are_blamed_in_observe_and_not_after_safe() -> None:
    rows = {row.mode: row for row in _by_slug()["tools"].rows}
    assert rows["observe"].user_caused_breaks > rows["safe"].user_caused_breaks


def test_short_prompt_is_not_blamed_on_the_app() -> None:
    for row in _by_slug()["short"].rows:
        assert row.user_caused_breaks == 0


def test_rewritten_history_is_blamed_on_the_app() -> None:
    rows = {row.mode: row for row in _by_slug()["rewrite"].rows}
    assert rows["observe"].user_caused_breaks >= 1
    assert rows["optimize"].user_caused_breaks >= 1
