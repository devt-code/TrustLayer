# Spike: pass-through logger

A throwaway experiment, to be deleted once the real gateway exists. It answers one question before any gateway code is written: what do real tool calls from Claude Desktop look like on the wire?

```
Claude Desktop ⇄ proxy.py (logs every message) ⇄ fake_server.py (the test range's fake tools)
```

- `proxy.py` starts a stdio MCP server as a child process and copies every message both ways, unchanged, logging each one. It uses only the standard library.
- `fake_server.py` is a minimal MCP server that serves the test range's fake tools. Nothing it does touches real files or the network.

## Run it

Add this entry under `mcpServers` in Claude Desktop's config, then restart Claude Desktop. The paths must be absolute, because Claude Desktop starts servers from its own folder. Use the project environment's Python: usually `.venv/bin/python`, or `~/.venvs/trustlayer/bin/python` when the project sits in an iCloud-synced Documents folder (see the main README).

```json
"trustlayer-spike": {
  "command": "/ABSOLUTE/PATH/TO/TrustLayer/.venv/bin/python",
  "args": ["/ABSOLUTE/PATH/TO/TrustLayer/spikes/passthrough/proxy.py"]
}
```

`claude_config.py` can add or remove that entry for you. Run it with the project environment's Python, and it fills in the right absolute paths. It refuses to touch a config that isn't valid JSON, and it leaves other entries alone:

```bash
.venv/bin/python spikes/passthrough/claude_config.py add      # or: remove
```

Then ask Claude something like "Use the trustlayer-spike tools to list the files in the workspace and read notes/release.md."

Every message is logged to `spikes/passthrough/spike.log`, which git ignores. Tool calls show up as lines with `TOOL CALL`:

```bash
tail -f spikes/passthrough/spike.log
```

## Things to look for

- The order of messages: `initialize`, then `notifications/initialized`, then `tools/list`, and only then any `tools/call`.
- What a tool call's `arguments` look like, and how the tool names appear to the client.
- Whether the client sends anything that identifies a session or a conversation. Stage 3 needs that for per-session state.

## Undo it

Remove the `trustlayer-spike` entry from the config (or restore the backup), then restart Claude Desktop.
