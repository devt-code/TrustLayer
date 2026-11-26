"""Throwaway spike: a tiny MCP server over stdio that serves the test range's fake tools.

It implements only what a client needs to list and call tools: initialize, ping,
tools/list and tools/call. Nothing here can touch real files or the network. The tools
act on an in-memory fake world, and "sent" emails go nowhere.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from trustlayer.testrange import ToolSpec, World, build_world

SERVER_INFO = {"name": "trustlayer-testrange", "version": "0.0.1"}
FALLBACK_PROTOCOL = "2025-06-18"


def handle(world: World, tools: dict[str, ToolSpec], method: str, params: dict[str, Any]) -> Any:
    if method == "initialize":
        # Good enough for a spike: answer with the client's own protocol version. The few
        # messages used here look the same in every version so far.
        version = params.get("protocolVersion", FALLBACK_PROTOCOL)
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {
            "tools": [
                {"name": name, "description": spec.description, "inputSchema": spec.input_schema()}
                for name, spec in tools.items()
            ]
        }
    if method == "tools/call":
        spec = tools.get(str(params.get("name", "")))
        if spec is None:
            text, is_error = f"Unknown tool: {params.get('name')}", True
        else:
            text, is_error = world.call(spec.name, params.get("arguments") or {})
        return {"content": [{"type": "text", "text": text}], "isError": is_error}
    raise LookupError(f"Method not found: {method}")


def main() -> None:
    world = build_world()
    # MCP clients expect names like files_read_file, so the dot becomes an underscore.
    tools = {spec.name.replace(".", "_"): spec for spec in world.tool_specs()}
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if not isinstance(message, dict) or "id" not in message or "method" not in message:
            continue  # notifications and responses need no reply
        reply: dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
        try:
            reply["result"] = handle(world, tools, message["method"], message.get("params") or {})
        except LookupError as exc:
            reply["error"] = {"code": -32601, "message": str(exc)}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
