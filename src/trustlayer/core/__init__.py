"""The pure decision core.

Rule: this package imports only the Python standard library and NumPy. It never touches
the network, the disk, the clock, MCP or any framework; the shell around it does all of
that and passes plain values in. tests/test_core_purity.py enforces the rule.
"""

from trustlayer.core.engine import inspect_call, inspect_result
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

__all__ = [
    "Action",
    "Decision",
    "Reason",
    "ResultDecision",
    "Session",
    "ToolCall",
    "ToolResult",
    "inspect_call",
    "inspect_result",
    "strictest",
]
