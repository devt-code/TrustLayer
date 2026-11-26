"""Every scenario file loads, the set covers what the plan asks for, and mistakes are caught."""

from __future__ import annotations

from pathlib import Path

import pytest

from trustlayer.sim.scenario import (
    CATEGORIES,
    Scenario,
    ScenarioError,
    load_scenario,
    load_scenarios,
)
from trustlayer.testrange.world import SPECS_BY_NAME

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"

VALID = """\
id: {name}
kind: normal
title: t
prompt: p
steps:
  - id: a
    tool: files.read_file
    args: {{path: README.md}}
answer: "{{{{ a }}}}"
expect:
  - answer_contains: Acme
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / f"{name}.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_all_scenarios_load() -> None:
    kinds = [s.kind for s in load_scenarios(SCENARIOS)]
    assert kinds.count("attack") >= 10
    assert kinds.count("normal") >= 10


def test_every_attack_category_is_covered() -> None:
    covered = {s.category for s in load_scenarios(SCENARIOS) if s.kind == "attack"}
    assert covered == set(CATEGORIES)


def _reads_untrusted_then_sends(scenario: Scenario) -> bool:
    seen_untrusted = False
    for step in scenario.steps:
        tags = SPECS_BY_NAME[step.attempts[0].tool].tags
        if seen_untrusted and "sends" in tags:
            return True
        seen_untrusted = seen_untrusted or "reads_untrusted" in tags
    return False


def test_normal_tasks_include_the_hard_case() -> None:
    """Real work that reads outside content and then sends something looks just like an
    attack. Without such tasks, the false-alarm numbers would only cover easy cases."""
    normal = [s for s in load_scenarios(SCENARIOS) if s.kind == "normal"]
    assert sum(_reads_untrusted_then_sends(s) for s in normal) >= 3


def test_a_valid_file_loads(tmp_path: Path) -> None:
    scenario = load_scenario(_write(tmp_path, "ok", VALID.format(name="ok")))
    assert scenario.steps[0].attempts[0].tool == "files.read_file"


@pytest.mark.parametrize(
    ("broken", "message"),
    [
        (VALID.format(name="other"), "file name"),
        (VALID.format(name="bad").replace("files.read_file", "files.steal"), "unknown tool"),
        (VALID.format(name="bad").replace("{{ a }}", "{{ b }}"), "unknown step"),
        (VALID.format(name="bad").replace("{{ a }}", "{{ a | rot13 }}"), "unknown filter"),
        (VALID.format(name="bad").replace("answer_contains", "answer_has"), "unknown condition"),
        (VALID.format(name="bad").replace("kind: normal", "kind: attack"), "category"),
        (VALID.format(name="bad") + "colour: blue\n", "unknown field"),
    ],
)
def test_mistakes_are_caught(tmp_path: Path, broken: str, message: str) -> None:
    with pytest.raises(ScenarioError, match=message):
        load_scenario(_write(tmp_path, "bad", broken))
