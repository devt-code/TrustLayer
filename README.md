# TrustLayer

TrustLayer is an open-source security gateway for AI agents. It sits between an agent, such as Claude Desktop or Claude Code, and the tools the agent uses through the Model Context Protocol (MCP). It checks every tool call and every tool result.

It assumes the agent will sometimes be fooled by a prompt injection. Its main job is making sure a fooled agent can't send data out or do damage.

**Status: foundations and baseline.** The decision core exists as a skeleton that allows everything, so every attack in the benchmark currently works. That is deliberate: it is the measured starting line that each defense will be compared against. See the [roadmap](docs/PLAN.md#11-roadmap).

**Results:** https://devt-code.github.io/trustlayer/

## Try it

You need [uv](https://docs.astral.sh/uv/). It installs Python 3.12 for the project by itself.

```bash
uv sync      # create .venv and install everything
make test    # run the tests
make eval    # run every scenario and write results/results.json
make site    # build the results page into _site/
```

On macOS, if the project folder is inside an iCloud-synced Documents folder, run `make install` instead of `uv sync`. iCloud marks dot-folders such as `.venv` as hidden, and Python 3.12 ignores hidden `.pth` files, which breaks the editable install. In that case the Makefile keeps the environment in `~/.venvs/trustlayer`.

## How the benchmark works

- **Test range** (`src/trustlayer/testrange/`): fake tools (files, an issue tracker, web pages, mail, chat, weather) that hold canary secrets. Nothing touches the real network or disk, and everything that leaves is recorded, so a leak is a fact rather than a guess.
- **Scenarios** (`scenarios/`): attacks and normal tasks written in YAML. See [scenarios/README.md](scenarios/README.md).
- **Worst-case agent** (`src/trustlayer/sim/`): a scripted agent that obeys every injected instruction it sees. The numbers then measure what the gateway stops, not what a model happens to refuse.
- **Rows**: every scenario runs once with no gateway and once through the TrustLayer core. Later rows add defenses one layer at a time.
- **Honest numbers**: every rate comes with a 95% confidence interval, because 10 out of 10 is not the same as 1,000 out of 1,000.

## Layout

```
src/trustlayer/core/       pure decision engine (standard library and NumPy only)
src/trustlayer/testrange/  fake tools with canary secrets, and the leak referee
src/trustlayer/sim/        scenario loader, worst-case agent, runner, scoring
src/trustlayer/eval/       metrics, the results file, the static results page
scenarios/                 attack and normal scenarios
spikes/                    throwaway experiments
docs/                      the plan and decision records
devlog/                    progress notes
```

## License

MIT
