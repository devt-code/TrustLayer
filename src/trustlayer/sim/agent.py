"""The worst-case agent: a scripted assistant that obeys every injection it reads.

It follows the scenario's steps for the user's task. As soon as any text that reached it
contains an injection's trigger, it drops what it is doing and carries out the attacker's
steps first, then goes back to the task. It can't be talked out of it. That is the
point: the numbers then measure what the gateway stops, not what a model happens to
refuse.

When a call is refused (blocked, or declined by the user), the agent tries that step's
fallbacks in order, the way a determined agent retries through another channel. If none
is left, the refusal message becomes the step's result.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from trustlayer.sim import template
from trustlayer.sim.scenario import Scenario, Step


@dataclass(frozen=True, slots=True)
class PlannedCall:
    """The call the agent wants to make next."""

    step_id: str
    attempt: int  # 0 for the plan, 1 and up for fallbacks
    tool: str
    args: Mapping[str, Any]
    injected: bool  # True if the attacker's instructions asked for it


class WorstCaseAgent:
    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self._queue: deque[tuple[Step, bool]] = deque((step, False) for step in scenario.steps)
        self._attempt = 0
        self._results: dict[str, str] = {}
        self._fired: set[int] = set()
        self.hijacked = False

    def observe(self, texts: Iterable[str]) -> None:
        """Read text that reaches the agent outside a tool result, like tool descriptions."""
        for text in texts:
            self._check_triggers(text)

    def next_call(self) -> PlannedCall | None:
        """The next call to make, or None when the agent is done."""
        if not self._queue:
            return None
        step, injected = self._queue[0]
        attempt = step.attempts[self._attempt]
        args = template.render_value(dict(attempt.args), self._results)
        return PlannedCall(step.id, self._attempt, attempt.tool, args, injected)

    def on_result(self, call: PlannedCall, delivered: str, raw: str) -> None:
        """The call ran. `delivered` is what the agent was given; `raw` is what the tool sent.

        Triggers are checked against the raw text: in the worst case, an injection that
        reached the agent in any form is understood and obeyed.
        """
        self._results[call.step_id] = delivered
        self._finish_step()
        self._check_triggers(raw)

    def on_refused(self, call: PlannedCall, message: str) -> None:
        """The call was not run. Try the next fallback, or give up on the step."""
        step, _ = self._queue[0]
        if self._attempt + 1 < len(step.attempts):
            self._attempt += 1
            return
        self._results[call.step_id] = message
        self._finish_step()

    def final_answer(self) -> str:
        """What the agent tells the user at the end."""
        return template.render(self._scenario.answer, self._results)

    def _finish_step(self) -> None:
        self._queue.popleft()
        self._attempt = 0

    def _check_triggers(self, text: str) -> None:
        new_steps: list[tuple[Step, bool]] = []
        for index, injection in enumerate(self._scenario.injections):
            if index in self._fired or injection.trigger not in text:
                continue
            self._fired.add(index)
            self.hijacked = True
            new_steps.extend((step, True) for step in injection.steps)
        # The attacker's steps jump the queue, in the order they were written.
        for item in reversed(new_steps):
            self._queue.appendleft(item)
