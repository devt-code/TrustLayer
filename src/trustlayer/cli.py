"""The `trustlayer` command.

trustlayer eval   run every scenario and write the results file
trustlayer site   build the static results page from the results file
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from trustlayer import __version__
from trustlayer.eval.report import evaluate, format_summary, write_results
from trustlayer.eval.site import build_site
from trustlayer.sim.scenario import ScenarioError, load_scenarios


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trustlayer", description="A security gateway for AI agents that use MCP tools."
    )
    parser.add_argument("--version", action="version", version=f"trustlayer {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    run_eval = commands.add_parser("eval", help="run every scenario and write the results file")
    run_eval.add_argument("--scenarios", default="scenarios", help="folder of scenario files")
    run_eval.add_argument("--out", default="results/results.json", help="results file to write")

    site = commands.add_parser("site", help="build the static results page")
    site.add_argument("--results", default="results/results.json", help="results file to read")
    site.add_argument("--out", default="_site", help="folder to write the page into")

    args = parser.parse_args(argv)
    if args.command == "eval":
        return _eval(args.scenarios, args.out)
    return _site(args.results, args.out)


def _eval(scenarios_dir: str, out: str) -> int:
    try:
        scenarios = load_scenarios(scenarios_dir)
    except ScenarioError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    results = evaluate(scenarios)
    path = write_results(results, out)
    print(format_summary(results))
    print(f"\nWrote {path}")
    return 0


def _site(results_path: str, out: str) -> int:
    path = Path(results_path)
    if not path.exists():
        print(f"error: {path} not found. Run `make eval` first.", file=sys.stderr)
        return 2
    results = json.loads(path.read_text(encoding="utf-8"))
    page = build_site(results, out)
    print(f"Wrote {page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
