"""Throwaway helper: add or remove the spike's entry in Claude Desktop's config.

    ~/.venvs/trustlayer/bin/python spikes/passthrough/claude_config.py add
    ~/.venvs/trustlayer/bin/python spikes/passthrough/claude_config.py remove

It refuses to touch a config that isn't valid JSON, leaves every other entry alone, and
prints exactly what it changed. Back the config up first anyway.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
NAME = "trustlayer-spike"
PROXY = Path(__file__).resolve().parent / "proxy.py"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("add", "remove"):
        print(__doc__)
        return 2
    if not CONFIG.exists():
        print(f"No Claude Desktop config found at {CONFIG}")
        return 1
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"The config is not valid JSON, so nothing was changed: {exc}")
        return 1
    if not isinstance(config, dict):
        print("The config is not a JSON object, so nothing was changed.")
        return 1

    servers = config.setdefault("mcpServers", {})
    if argv[1] == "add":
        # sys.executable is the Python running this script: the project environment's.
        servers[NAME] = {"command": sys.executable, "args": [str(PROXY)]}
        change = {NAME: servers[NAME]}
    elif servers.pop(NAME, None) is None:
        print(f"There is no {NAME!r} entry, so nothing was changed.")
        return 0
    else:
        change = {NAME: "removed"}

    CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {CONFIG}")
    print(json.dumps(change, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
