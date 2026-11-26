# 001: Foundations and the baseline

- **Status:** accepted
- **Date:** 2026-11-25

## Context

Before any defense exists, the project needs a starting line it can measure against: a test range where a leak is provable, scenarios that exercise every attack category, and an agent that is fooled every time. Every later number is a comparison with this baseline, so the baseline itself has to be trustworthy.

## Decisions

### 1. A pure core built from plain dataclasses

- **Options:** Pydantic models; plain dicts; frozen standard-library dataclasses.
- **Choice:** frozen dataclasses. `inspect_call` and `inspect_result` take a `Session` and return a decision plus a **new** `Session`, so the core never changes anything in place.
- **Why:** the core may import only the standard library and NumPy. Immutable values make every step replayable, which the replay viewer will need, and easy to property-test. Pydantic stays at the edges (the gateway and the API), where outside input gets validated.
- **Evidence:** `tests/test_core_purity.py` reads the core's source and fails on any other import, or on any call to `open`, `print` and similar built-ins.

### 2. A scripted worst-case agent with triggers

- **Options:** a real model; a fixed script that always runs the attack; a script whose attack steps start only once the injection has actually reached the agent.
- **Choice:** the third. Each attack names a `trigger`, a phrase from the injected text. When the trigger appears in anything the agent reads (a tool result or a tool description), the attacker's steps run next.
- **Why:** the numbers then measure what the gateway stops, not what a model happens to refuse. And if a defense stops the poisoned content from arriving at all, the attack correctly never starts.
- **Also:** fallbacks per step model an agent that retries through other channels after a block.

### 3. The leak referee decodes, and adds up pieces

- **Choice:** a canary counts as leaked when every character of it appeared in outbound data, in pieces of six or more characters, including after URL-decoding and base64-decoding.
- **Why:** "the canary string appears in an email" would miss secrets hidden in URLs, encoded, or sent a few characters at a time. Those are attack categories 5 and 7.
- **Known limit:** pieces shorter than six characters are not counted.

### 4. Canary values in a format of their own

- **Choice:** `TLCANARY-<name>-<hex>`.
- **Why:** canaries that looked like real AWS or Stripe keys would trip GitHub's secret scanning and could block a push. A distinct prefix also makes exact matching trivial.

### 5. A Python-generated results page for now

- **Options:** start the React app now; generate static HTML from Python.
- **Choice:** static HTML from Python, with no JavaScript. It is rebuilt and deployed by CI on every push to `main`.
- **Why:** this stage needs only a table of results. React arrives when replays need interactivity.

### 6. Honest numbers from the start

- Every rate is reported with a 95% Wilson confidence interval. With 10 attacks, "100%" fits anything from 72% to 100%.
- There are two rows from the start: **no gateway**, and **the TrustLayer core**. With no gateway, every attack must work and every normal task must complete (`tests/test_baseline.py`). That keeps the benchmark itself honest in every later stage.
- Three of the ten normal tasks read untrusted content and then send something. That is the hardest case for false alarms, so it is in the baseline from day one.

### 7. Layout changes from the plan

- `spikes/` holds throwaway experiments. The first one is a pass-through logger between Claude Desktop and a fake MCP server.
- Generated output goes to `results/` and `_site/`. Neither is committed, because CI rebuilds both on every push.

## Consequences

- The first measured result is the baseline: every attack works and every normal task completes, in both rows.
- New layers plug into the core in the fixed pipeline order, and each new row of the results table shows exactly what that layer added.
