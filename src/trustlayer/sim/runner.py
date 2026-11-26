"""Runs one scenario: the worst-case agent, the gateway (or none), and the test range.

This is the imperative shell around the core. It turns the agent's steps into events,
asks the core for decisions, runs allowed calls against the fake tools, and records
everything for scoring. It also times the core, because we measure before we optimize.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from trustlayer.core import (
    Action,
    Decision,
    Reason,
    Session,
    ToolCall,
    ToolResult,
    inspect_call,
    inspect_result,
)
from trustlayer.sim.agent import PlannedCall, WorstCaseAgent
from trustlayer.sim.scenario import Scenario
from trustlayer.testrange import World, build_world

MAX_CALLS = 100  # a safety stop, in case a scenario makes the agent loop


@dataclass(frozen=True, slots=True)
class Row:
    """One configuration that every scenario runs under: one row of the results table."""

    name: str
    label: str
    description: str
    gateway: bool  # False: calls go straight to the tools


ROWS: tuple[Row, ...] = (
    Row(
        name="no-gateway",
        label="No gateway",
        description="The agent's calls go straight to the tools.",
        gateway=False,
    ),
    Row(
        name="trustlayer",
        label="TrustLayer core",
        description="Every call and result passes through the core. No checks are enabled yet.",
        gateway=True,
    ),
)


@dataclass(frozen=True, slots=True)
class CallRecord:
    """What happened to one call the agent tried to make."""

    step_id: str
    attempt: int
    injected: bool
    tool: str
    args: dict[str, Any]
    action: str  # allow, ask or block
    reasons: tuple[Reason, ...]
    approved: bool | None  # the simulated user's answer, when the action was ask
    executed: bool
    is_error: bool
    core_ns: int  # time spent inside the core for this call and its result


@dataclass(slots=True)
class Run:
    """Everything that happened in one scenario run."""

    scenario: Scenario
    row: Row
    world: World
    calls: list[CallRecord] = field(default_factory=list)
    answer: str = ""
    hijacked: bool = False
    truncated: bool = False


_STRAIGHT_THROUGH = Decision(Action.ALLOW)


def run_scenario(scenario: Scenario, row: Row, *, user_approves: bool = False) -> Run:
    """Run one scenario under one row.

    `user_approves` is how the simulated user answers "ask" decisions. The default is a
    careful user who says no.
    """
    world = build_world(scenario.fixtures)
    agent = WorstCaseAgent(scenario)
    session = Session(session_id=scenario.id)
    run = Run(scenario=scenario, row=row, world=world)

    # An agent reads every tool description when it connects, so tool poisoning starts here.
    agent.observe(spec.description for spec in world.tool_specs())

    while (planned := agent.next_call()) is not None:
        if len(run.calls) >= MAX_CALLS:
            run.truncated = True
            break
        call = _to_event(scenario.id, len(run.calls) + 1, planned)
        core_ns = 0

        if row.gateway:
            start = time.perf_counter_ns()
            decision, session = inspect_call(session, call)
            core_ns += time.perf_counter_ns() - start
        else:
            decision = _STRAIGHT_THROUGH

        approved = user_approves if decision.action == Action.ASK else None
        proceed = decision.action == Action.ALLOW or approved is True

        executed = False
        is_error = False
        if proceed:
            raw, is_error = world.call(planned.tool, planned.args)
            executed = True
            delivered = raw
            if row.gateway:
                start = time.perf_counter_ns()
                result_decision, session = inspect_result(
                    session, call, ToolResult(call.call_id, raw, is_error)
                )
                core_ns += time.perf_counter_ns() - start
                delivered = result_decision.content
            agent.on_result(planned, delivered, raw)
        else:
            agent.on_refused(planned, _refusal_message(decision, approved))

        run.calls.append(
            CallRecord(
                step_id=planned.step_id,
                attempt=planned.attempt,
                injected=planned.injected,
                tool=planned.tool,
                args=dict(planned.args),
                action=decision.action.label,
                reasons=decision.reasons,
                approved=approved,
                executed=executed,
                is_error=is_error,
                core_ns=core_ns,
            )
        )

    run.answer = agent.final_answer()
    run.hijacked = agent.hijacked
    return run


def _to_event(session_id: str, number: int, planned: PlannedCall) -> ToolCall:
    server, _, tool = planned.tool.partition(".")
    return ToolCall(
        session_id=session_id,
        call_id=f"{session_id}#{number}",
        server=server,
        tool=tool,
        arguments=dict(planned.args),
    )


def _refusal_message(decision: Decision, approved: bool | None) -> str:
    why = "; ".join(reason.message for reason in decision.reasons) or "no reason given"
    if approved is False:
        return f"The user declined this action. ({why})"
    return f"Blocked by TrustLayer: {why}"
