"""The core skeleton allows everything, explains itself, and never edits its input.

The strictest-wins tests are property tests: Hypothesis tries hundreds of random inputs
looking for one that breaks the rule.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from trustlayer.core import (
    Action,
    Session,
    ToolCall,
    ToolResult,
    inspect_call,
    inspect_result,
    strictest,
)

names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20)
arguments = st.dictionaries(names, st.text(max_size=200), max_size=5)
actions = st.sampled_from(list(Action))


@given(server=names, tool=names, args=arguments)
def test_every_call_is_allowed_for_now(server: str, tool: str, args: dict[str, str]) -> None:
    session = Session(session_id="s1")
    call = ToolCall(session_id="s1", call_id="c1", server=server, tool=tool, arguments=args)
    decision, new_session = inspect_call(session, call)
    assert decision.action == Action.ALLOW
    assert decision.reasons, "every decision says why"
    assert new_session.calls_seen == 1
    assert session.calls_seen == 0, "the input session must not change"


@given(content=st.text(max_size=2000), is_error=st.booleans())
def test_results_pass_through_unchanged_for_now(content: str, is_error: bool) -> None:
    session = Session(session_id="s1")
    call = ToolCall(session_id="s1", call_id="c1", server="files", tool="read_file")
    decision, new_session = inspect_result(session, call, ToolResult("c1", content, is_error))
    assert decision.content == content
    assert decision.labels == frozenset()
    assert new_session.results_seen == 1


@given(st.lists(actions, max_size=6))
def test_strictest_is_the_most_severe_answer(items: list[Action]) -> None:
    assert strictest(*items) == max(items, default=Action.ALLOW)


@given(actions, actions)
def test_strictest_ignores_order(a: Action, b: Action) -> None:
    assert strictest(a, b) == strictest(b, a)


@given(actions, actions, actions)
def test_strictest_ignores_grouping(a: Action, b: Action, c: Action) -> None:
    assert strictest(strictest(a, b), c) == strictest(a, strictest(b, c))


@given(actions)
def test_allow_never_loosens_and_block_always_wins(a: Action) -> None:
    assert strictest(a, Action.ALLOW) == a
    assert strictest(a, Action.BLOCK) == Action.BLOCK


def test_actions_are_ordered_block_over_ask_over_allow() -> None:
    assert Action.ALLOW < Action.ASK < Action.BLOCK
    assert strictest() == Action.ALLOW
    assert Action.BLOCK.label == "block"
