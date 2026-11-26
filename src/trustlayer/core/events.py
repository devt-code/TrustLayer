"""The event schema: the values that flow into and out of the decision core.

Everything here is a plain, immutable value. The shell (the gateway, the demo, the eval)
builds these from MCP messages or scenario steps, hands them to the core, and acts on
what comes back.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class Action(IntEnum):
    """What to do with a tool call. A higher value is stricter."""

    ALLOW = 0
    ASK = 1
    BLOCK = 2

    @property
    def label(self) -> str:
        return self.name.lower()


def strictest(*actions: Action) -> Action:
    """Combine the answers of several checks: block beats ask beats allow.

    With nothing to combine, the answer is allow.
    """
    return max(actions, default=Action.ALLOW)


@dataclass(frozen=True, slots=True)
class Reason:
    """One explanation for a decision, tied to the layer that produced it."""

    layer: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ToolCall:
    """An agent asking a tool server to run one of its tools."""

    session_id: str
    call_id: str
    server: str
    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """The qualified tool name, for example `files.read_file`."""
        return f"{self.server}.{self.tool}"


@dataclass(frozen=True, slots=True)
class ToolResult:
    """What a tool server sent back for one call."""

    call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class Decision:
    """The core's answer for an outgoing call."""

    action: Action
    reasons: tuple[Reason, ...] = ()


@dataclass(frozen=True, slots=True)
class ResultDecision:
    """The core's answer for an incoming result: the content to pass on, plus labels."""

    content: str
    labels: frozenset[str] = frozenset()
    reasons: tuple[Reason, ...] = ()


@dataclass(frozen=True, slots=True)
class Session:
    """What the core remembers about one agent session.

    The core never changes a Session in place. It returns a new one, so every step of a
    run can be replayed and inspected later.
    """

    session_id: str
    calls_seen: int = 0
    results_seen: int = 0
