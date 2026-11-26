"""Throwaway spike: a pass-through between an MCP client and an MCP server, over stdio.

Claude Desktop starts this script as if it were a tool server. The script starts the
real server as a child process and copies every message both ways, unchanged, logging
each one. It exists to see what real tool calls look like before the gateway is built.

    python spikes/passthrough/proxy.py                 # wraps the fake test-range server
    python spikes/passthrough/proxy.py -- CMD ARGS...  # wraps any stdio MCP server

Logs go to stderr, which Claude Desktop saves, and to spikes/passthrough/spike.log.
Stdout carries the protocol itself, so nothing else may ever be printed there.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import BinaryIO

HERE = Path(__file__).resolve().parent
LOG_PATH = HERE / "spike.log"
_log_lock = threading.Lock()
_done = threading.Event()


def log(line: str) -> None:
    text = f"[{time.strftime('%H:%M:%S')}] {line}"
    with _log_lock:
        print(text, file=sys.stderr, flush=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")


def describe(direction: str, raw: bytes) -> str:
    """One readable log line for one JSON-RPC message."""
    try:
        message = json.loads(raw)
    except ValueError:
        return f"{direction} (not JSON) {raw[:200]!r}"
    if not isinstance(message, dict):
        return f"{direction} {str(message)[:200]}"
    method = message.get("method")
    if method == "tools/call":
        params = message.get("params") or {}
        arguments = json.dumps(params.get("arguments", {}), ensure_ascii=False)
        return f"{direction} TOOL CALL id={message.get('id')} name={params.get('name')} arguments={arguments}"
    if method:
        return f"{direction} {method} id={message.get('id', '-')}"
    if "error" in message:
        return f"{direction} error for id={message.get('id')}: {json.dumps(message['error'])[:300]}"
    result = json.dumps(message.get("result"), ensure_ascii=False)
    return f"{direction} result for id={message.get('id')}: {result[:300]}"


def pump(source: BinaryIO, sink: BinaryIO, direction: str) -> None:
    """Copy newline-delimited messages from source to sink until either side closes."""
    try:
        for raw in iter(source.readline, b""):
            sink.write(raw)
            sink.flush()
            log(describe(direction, raw.strip()))
    except OSError as exc:  # includes BrokenPipeError, when the other side has gone
        log(f"{direction} stopped: {exc}")
    finally:
        _done.set()


def main() -> int:
    if "--" in sys.argv:
        command = sys.argv[sys.argv.index("--") + 1 :]
    else:
        command = [sys.executable, str(HERE / "fake_server.py")]
    if not command:
        log("usage: proxy.py [-- CMD ARGS...]")
        return 2

    log(f"starting server: {' '.join(command)}")
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert child.stdin is not None and child.stdout is not None
    for source, sink, direction in (
        (sys.stdin.buffer, child.stdin, "client -> server"),
        (child.stdout, sys.stdout.buffer, "server -> client"),
    ):
        threading.Thread(target=pump, args=(source, sink, direction), daemon=True).start()

    _done.wait()  # one side closed: the client quit, or the server died
    try:
        child.stdin.close()
    except OSError:
        pass
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.terminate()
    log("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
