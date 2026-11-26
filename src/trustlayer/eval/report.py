"""Runs every scenario under every row and builds the results file.

The results file is the single source for the console summary, the results page and CI.
"""

from __future__ import annotations

import json
import os
import platform
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trustlayer import __version__
from trustlayer.eval.metrics import percentile, wilson_interval
from trustlayer.sim.runner import ROWS, CallRecord, Row, Run, run_scenario
from trustlayer.sim.scenario import CATEGORIES, Scenario
from trustlayer.sim.scoring import Outcome, score
from trustlayer.testrange.canaries import CANARIES

SCHEMA_VERSION = 1
ARGS_PREVIEW = 300  # characters of each call's arguments kept in the results file


def evaluate(scenarios: Sequence[Scenario], rows: Sequence[Row] = ROWS) -> dict[str, Any]:
    started = time.perf_counter()
    row_reports = []
    for row in rows:
        runs = [run_scenario(scenario, row) for scenario in scenarios]
        outcomes = [score(run) for run in runs]
        row_reports.append(_row_report(row, runs, outcomes))
    elapsed = time.perf_counter() - started
    return {
        "schema": SCHEMA_VERSION,
        "version": __version__,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": os.environ.get("GITHUB_SHA"),
        "python": platform.python_version(),
        "elapsed_seconds": round(elapsed, 4),
        "scenario_counts": {
            kind: sum(s.kind == kind for s in scenarios) for kind in ("attack", "normal")
        },
        "categories": CATEGORIES,
        "rows": row_reports,
    }


def write_results(results: dict[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def format_summary(results: dict[str, Any]) -> str:
    """The table printed after `make eval`."""
    counts = results["scenario_counts"]
    lines = [
        f"TrustLayer eval: {counts['attack']} attacks and {counts['normal']} normal tasks "
        f"in {results['elapsed_seconds']:.2f} s",
        "",
        f"{'Row':<17}{'Attacks that worked':<32}{'Normal tasks done':<32}{'Prompts/task':<14}Core p95",
    ]
    for row in results["rows"]:
        s = row["summary"]
        attacks = _count_cell(s["attack_successes"], s["attacks"], s["attack_success_ci95"])
        normal = _count_cell(s["normal_completed"], s["normal_tasks"], s["normal_completion_ci95"])
        prompts = (
            "-" if s["prompts_per_normal_task"] is None else f"{s['prompts_per_normal_task']:.2f}"
        )
        p95 = "-" if s["core_us_p95"] is None else f"{s['core_us_p95']:.1f} us"
        lines.append(f"{row['label']:<17}{attacks:<32}{normal:<32}{prompts:<14}{p95}")
    lines += ["", "Brackets show the 95% confidence interval."]
    return "\n".join(lines)


def _count_cell(hits: int, total: int, ci: list[float]) -> str:
    if total == 0:
        return "-"
    return f"{hits}/{total} {hits / total:.0%} [{ci[0]:.0%}-{ci[1]:.0%}]"


def _row_report(row: Row, runs: list[Run], outcomes: list[Outcome]) -> dict[str, Any]:
    attacks = [o for o in outcomes if o.kind == "attack"]
    normals = [o for o in outcomes if o.kind == "normal"]
    worked = sum(o.succeeded for o in attacks)
    done = sum(o.succeeded for o in normals)
    core_us = [c.core_ns / 1000 for run in runs for c in run.calls] if row.gateway else []
    summary = {
        "attacks": len(attacks),
        "attack_successes": worked,
        "attack_success_rate": _rate(worked, len(attacks)),
        "attack_success_ci95": list(wilson_interval(worked, len(attacks))),
        "attacks_stopped_only_by_asking": sum(o.stopped_by_user for o in attacks),
        "normal_tasks": len(normals),
        "normal_completed": done,
        "normal_completion_rate": _rate(done, len(normals)),
        "normal_completion_ci95": list(wilson_interval(done, len(normals))),
        "prompts_per_normal_task": _rate(sum(o.asks for o in normals), len(normals)),
        "normal_tasks_with_a_block": sum(o.blocks > 0 for o in normals),
        "calls": sum(len(run.calls) for run in runs),
        "core_us_p50": _round(percentile(core_us, 50)),
        "core_us_p95": _round(percentile(core_us, 95)),
    }
    return {
        "name": row.name,
        "label": row.label,
        "description": row.description,
        "summary": summary,
        "scenarios": [_scenario_report(r, o) for r, o in zip(runs, outcomes, strict=True)],
    }


def _scenario_report(run: Run, outcome: Outcome) -> dict[str, Any]:
    scenario = run.scenario
    return {
        "id": scenario.id,
        "kind": scenario.kind,
        "category": scenario.category,
        "family": scenario.family,
        "title": scenario.title,
        "prompt": scenario.prompt,
        "succeeded": outcome.succeeded,
        "met": list(outcome.met),
        "leaked": list(outcome.leaked),
        "hijacked": run.hijacked,
        "asks": outcome.asks,
        "blocks": outcome.blocks,
        "stopped_by": outcome.stopped_by,
        "stopped_by_user": outcome.stopped_by_user,
        "calls": [_call_report(call) for call in run.calls],
    }


def _call_report(call: CallRecord) -> dict[str, Any]:
    args = json.dumps(call.args, ensure_ascii=False, sort_keys=True)
    return {
        "step": call.step_id,
        "attempt": call.attempt,
        "injected": call.injected,
        "tool": call.tool,
        "args": _mask(args)[:ARGS_PREVIEW],
        "action": call.action,
        "approved": call.approved,
        "executed": call.executed,
        "is_error": call.is_error,
        "reasons": [{"layer": r.layer, "code": r.code, "message": r.message} for r in call.reasons],
        "core_us": round(call.core_ns / 1000, 2),
    }


def _mask(text: str) -> str:
    """Replace canary values with their names. Canaries are fake, but secrets never go
    into a record in plain text, and that habit starts here."""
    for cid, value in CANARIES.items():
        text = text.replace(value, f"[canary:{cid}]")
    return text


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)
