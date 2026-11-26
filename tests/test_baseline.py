"""The baseline: with no defenses, every attack works and every normal task gets done.

This checks the benchmark itself. An attack that fails with no gateway is a broken
scenario, and a normal task that fails with no gateway is a broken task. These tests keep
the "no gateway" row honest in every later stage too.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from trustlayer.sim.runner import ROWS, run_scenario
from trustlayer.sim.scenario import Scenario, load_scenarios
from trustlayer.sim.scoring import score

SCENARIOS = load_scenarios(Path(__file__).resolve().parents[1] / "scenarios")
ROW = {row.name: row for row in ROWS}


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_with_no_gateway_attacks_work_and_tasks_get_done(scenario: Scenario) -> None:
    run = run_scenario(scenario, ROW["no-gateway"])
    outcome = score(run)
    assert not run.truncated, "the agent hit the call limit"
    if scenario.kind == "attack":
        assert run.hijacked, "the injection's trigger never reached the agent"
        assert outcome.succeeded, "the attack failed even with no defenses"
    else:
        assert not run.hijacked
        assert outcome.succeeded, "the normal task was not completed"
        assert not outcome.leaked, "a normal task leaked a canary"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_the_core_skeleton_changes_nothing(scenario: Scenario) -> None:
    plain = score(run_scenario(scenario, ROW["no-gateway"]))
    gated_run = run_scenario(scenario, ROW["trustlayer"])
    gated = score(gated_run)
    assert gated.succeeded == plain.succeeded
    assert gated.leaked == plain.leaked
    assert gated.asks == 0 and gated.blocks == 0
    assert all(call.core_ns >= 0 for call in gated_run.calls)
