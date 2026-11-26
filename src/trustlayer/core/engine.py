"""The two entry points of the decision core.

For now both allow everything. This is the baseline that every later defense is measured
against. The order of the checks that later stages fill in is fixed:

Outgoing calls:
    1. pinning            2. rules             3. cleaning and detectors
    4. taint, provenance and session rules     5. classifier and scorecard
    6. Gemma, only for unclear cases and data-sending calls in tainted sessions
    7. the decision: the strictest answer wins (block beats ask beats allow)

Incoming results:
    cleaning, then scanning, then labelling.
"""

from __future__ import annotations

from dataclasses import replace

from trustlayer.core.events import (
    Action,
    Decision,
    Reason,
    ResultDecision,
    Session,
    ToolCall,
    ToolResult,
    strictest,
)

_NO_CHECKS = Reason(
    layer="baseline",
    code="baseline.allow_all",
    message="No checks are enabled yet, so every call is allowed.",
)


def inspect_call(session: Session, call: ToolCall) -> tuple[Decision, Session]:
    """Decide what happens to an outgoing tool call.

    Returns the decision and the updated session.
    """
    layer_actions: list[Action] = []  # each layer will add its answer here
    decision = Decision(action=strictest(*layer_actions), reasons=(_NO_CHECKS,))
    return decision, replace(session, calls_seen=session.calls_seen + 1)


def inspect_result(
    session: Session, call: ToolCall, result: ToolResult
) -> tuple[ResultDecision, Session]:
    """Check what a tool sent back, before the agent sees it.

    Returns the content to pass on (unchanged for now) and the updated session.
    """
    decision = ResultDecision(content=result.content)
    return decision, replace(session, results_seen=session.results_seen + 1)
