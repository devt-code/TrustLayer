# 2026-11-25: Foundations and the baseline

## What exists now

- **A pure decision core:** the event schema plus two entry points, `inspect_call` and `inspect_result`. Both allow everything for now. A test reads the core's source and fails if it ever imports anything beyond the standard library and NumPy.
- **A test range:** 13 fake tools across six servers (files, issues, web, mail, chat, weather), with five canary secrets planted in private files. Everything that leaves the range is recorded.
- **A leak referee:** finds a canary even when it was URL-encoded, base64-encoded or sent in pieces across several calls.
- **20 scenarios:** 10 attacks covering all eight attack categories, and 10 normal tasks.
  - Three of the normal tasks read untrusted content and then send something. That is the hardest case for false alarms.
- **A worst-case agent:** obeys every injection as soon as it reads the trigger text, and retries through other channels when a call is refused.
- **Tooling:** `make eval`, a static results page, and CI that runs the tests and the eval and then deploys the page.

## The baseline

| Row | Attacks that worked | Normal tasks completed | Prompts per task | Core time per call (p95) |
|---|---|---|---|---|
| No gateway | 10/10 (95% CI 72–100%) | 10/10 | 0.00 | – |
| TrustLayer core | 10/10 (95% CI 72–100%) | 10/10 | 0.00 | 6.7 µs |

- Every attack works because no defense exists yet. That is deliberate: this is the line that every layer will be measured against.
- The interval matters too. With 10 attacks, "100%" fits any true rate from 72% to 100%, which is why the suite will grow.
- 89 tests pass in about 1.5 s. The whole eval runs in a few milliseconds.

## The Claude Desktop spike

A throwaway pass-through (`spikes/passthrough/`) sat between Claude Desktop and a fake MCP server, logging every message. It showed:

- **The handshake:** `initialize`, then `notifications/initialized`, then `tools/list`, all before any tool call. Claude Desktop asked for MCP protocol version `2025-11-25`.
- **Server processes:** the server was started twice within 20 seconds, so the gateway can't assume one server process per user.
- **What a call carries:** a tool name and its arguments, for example `files_read_file` with `{"path": ".env"}`.
  - Three real calls were recorded: listing the workspace, reading `notes/release.md`, and reading `.env`.
- **The client's own prompt:** calls that the user declines at Claude Desktop's permission prompt never reach the server. A gateway sits behind that prompt, so it only ever sees calls the client has already let through.
- **Nothing stopped the third call.** The agent read `.env` and showed both canary secrets in the chat. That is the baseline in miniature: the next stage's policy rules exist to block exactly this read.

## Next

Deterministic defenses: the policy engine, cleaning and detectors, pinning, taint, provenance and session rules, with the promises P1–P8 as tests.
