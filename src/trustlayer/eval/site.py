"""Builds the static results page from a results file.

The page is plain HTML and CSS: no JavaScript, nothing loaded from anywhere else. Every
piece of text taken from the results is escaped, so a scenario can never inject markup.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

REPO_URL = "https://github.com/devt-code/TrustLayer"

LEDE = (
    "TrustLayer is an open-source security gateway for AI agents. Every scenario below runs "
    "against fake tools that hold canary secrets, so a leak is a recorded fact, not a guess."
)

STATUS_NOTE = (
    "Baseline: no defenses are enabled yet, so every attack is expected to work. This is the "
    "starting line that each new layer will be measured against."
)

CSS = """
:root { color-scheme: light dark;
  --bg: #fbfbfa; --fg: #1d1d1f; --muted: #5f6368; --card: #ffffff; --line: #e3e3e0;
  --accent: #1d4ed8; --bad: #b42318; --bad-bg: #fde7e4; --good: #067647; --good-bg: #dcfae6;
  --warn: #93370d; --warn-bg: #fef0c7; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #111214; --fg: #ececec; --muted: #a0a4a8; --card: #1a1b1e; --line: #2c2e33;
    --accent: #8ab4ff; --bad: #ffb4a8; --bad-bg: #4a1d17; --good: #a6f4c5; --good-bg: #0f3b26;
    --warn: #fedf89; --warn-bg: #4a3108; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1000px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 1.9rem; margin: 0 0 6px; }
h2 { font-size: 1.2rem; margin: 40px 0 12px; }
a { color: var(--accent); }
code { font-family: ui-monospace, Menlo, monospace; font-size: .9em; }
.lede { color: var(--muted); margin: 0 0 20px; max-width: 70ch; }
.note { margin: 0; padding: 12px 16px; background: var(--card); border: 1px solid var(--line);
  border-left: 4px solid var(--accent); border-radius: 8px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px;
  margin-top: 20px; }
.tile { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
  padding: 14px 16px; }
.tile .label { color: var(--muted); font-size: .85rem; }
.tile .value { font-size: 1.8rem; font-weight: 650; font-variant-numeric: tabular-nums; }
.tile .sub { color: var(--muted); font-size: .8rem; }
.table-wrap { overflow-x: auto; background: var(--card); border: 1px solid var(--line);
  border-radius: 10px; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line);
  vertical-align: top; }
th { color: var(--muted); font-size: .78rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: .03em; }
tr:last-child td { border-bottom: 0; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.sub-id { display: block; color: var(--muted); font-size: .78rem;
  font-family: ui-monospace, Menlo, monospace; }
.badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: .78rem;
  font-weight: 600; white-space: nowrap; }
.bad { color: var(--bad); background: var(--bad-bg); }
.good { color: var(--good); background: var(--good-bg); }
.warn { color: var(--warn); background: var(--warn-bg); }
footer { margin-top: 40px; color: var(--muted); font-size: .85rem; }
"""


def build_site(results: dict[str, Any], out_dir: str | Path) -> Path:
    """Write index.html and a copy of the results file into `out_dir`."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    page = out / "index.html"
    page.write_text(render_page(results), encoding="utf-8")
    data = json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    (out / "results.json").write_text(data, encoding="utf-8")
    return page


def render_page(results: dict[str, Any]) -> str:
    rows = results["rows"]
    body = "\n".join(
        [
            "<main>",
            "<h1>TrustLayer results</h1>",
            f'<p class="lede">{_e(LEDE)}</p>',
            f'<p class="note">{_e(STATUS_NOTE)}</p>',
            _tiles(rows[-1]),  # the last row is the full TrustLayer configuration
            "<h2>By configuration</h2>",
            _rows_table(rows),
            "<h2>Scenarios</h2>",
            _scenarios_table(results, rows),
            _footer(results),
            "</main>",
        ]
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>TrustLayer results</title>\n"
        '<meta name="description" content="Benchmark results for TrustLayer, '
        'a security gateway for AI agents.">\n'
        f"<style>{CSS}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def _tiles(row: dict[str, Any]) -> str:
    s = row["summary"]
    tiles = [
        (
            "Attacks that worked",
            _pct(s["attack_success_rate"]),
            f"{s['attack_successes']} of {s['attacks']} · 95% CI {_ci(s['attack_success_ci95'])}",
        ),
        (
            "Normal tasks completed",
            _pct(s["normal_completion_rate"]),
            f"{s['normal_completed']} of {s['normal_tasks']} · 95% CI {_ci(s['normal_completion_ci95'])}",
        ),
        (
            "Prompts per normal task",
            _num(s["prompts_per_normal_task"]),
            "How often the user had to approve something",
        ),
        (
            "Time in the core per call",
            _us(s["core_us_p95"]),
            "95th percentile, measured during the eval",
        ),
    ]
    items = "".join(
        f'<div class="tile"><div class="label">{_e(label)}</div>'
        f'<div class="value">{_e(value)}</div><div class="sub">{_e(sub)}</div></div>'
        for label, value, sub in tiles
    )
    return f'<div class="tiles">{items}</div>'


def _rows_table(rows: list[dict[str, Any]]) -> str:
    header = (
        "<tr><th>Configuration</th><th>Attacks that worked</th><th>Normal tasks completed</th>"
        "<th>Prompts per task</th><th>Core time p95</th></tr>"
    )
    lines = []
    for row in rows:
        s = row["summary"]
        lines.append(
            "<tr>"
            f'<td>{_e(row["label"])}<span class="sub-id">{_e(row["description"])}</span></td>'
            f'<td class="num">{_e(_fraction(s["attack_successes"], s["attacks"]))}</td>'
            f'<td class="num">{_e(_fraction(s["normal_completed"], s["normal_tasks"]))}</td>'
            f'<td class="num">{_e(_num(s["prompts_per_normal_task"]))}</td>'
            f'<td class="num">{_e(_us(s["core_us_p95"]))}</td>'
            "</tr>"
        )
    return _table(header, lines)


def _scenarios_table(results: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    categories = results.get("categories", {})
    header = (
        "<tr><th>Scenario</th><th>Kind</th><th>Category</th>"
        + "".join(f"<th>{_e(row['label'])}</th>" for row in rows)
        + "</tr>"
    )
    by_row = [{sc["id"]: sc for sc in row["scenarios"]} for row in rows]
    lines = []
    for sc in rows[0]["scenarios"]:
        category = categories.get(sc["category"], sc["category"]) if sc["category"] else "-"
        cells = "".join(f"<td>{_badge(lookup.get(sc['id']))}</td>" for lookup in by_row)
        lines.append(
            "<tr>"
            f'<td>{_e(sc["title"])}<span class="sub-id">{_e(sc["id"])}</span></td>'
            f"<td>{_e(sc['kind'])}</td><td>{_e(category)}</td>{cells}"
            "</tr>"
        )
    return _table(header, lines)


def _table(header: str, lines: list[str]) -> str:
    body = "".join(lines)
    return (
        f'<div class="table-wrap"><table><thead>{header}</thead><tbody>{body}</tbody></table></div>'
    )


def _badge(sc: dict[str, Any] | None) -> str:
    if sc is None:
        return "-"
    if sc["kind"] == "attack":
        css, text = ("bad", "worked") if sc["succeeded"] else ("good", "stopped")
    else:
        css, text = ("good", "done") if sc["succeeded"] else ("warn", "not done")
    return f'<span class="badge {css}">{_e(text)}</span>'


def _footer(results: dict[str, Any]) -> str:
    commit = results.get("commit")
    if commit:
        source = (
            f'commit <a href="{_e(REPO_URL)}/commit/{_e(commit)}"><code>{_e(commit[:7])}</code></a>'
        )
    else:
        source = "a local run"
    return (
        "<footer>"
        f"<p>Generated {_e(results['generated_at'])} from {source}, Python {_e(results['python'])}, "
        f"in {_e(format(results['elapsed_seconds'], '.2f'))} s. "
        "Rerun it yourself with <code>make eval</code>.</p>"
        f'<p><a href="results.json">Raw results (JSON)</a> · <a href="{_e(REPO_URL)}">Source</a> · '
        f'<a href="{_e(REPO_URL)}/blob/main/docs/PLAN.md">Plan</a></p>'
        "</footer>"
    )


def _e(value: Any) -> str:
    return escape(str(value))


def _fraction(hits: int, total: int) -> str:
    return "-" if not total else f"{hits}/{total} ({hits / total:.0%})"


def _pct(rate: float | None) -> str:
    return "-" if rate is None else f"{rate:.0%}"


def _ci(interval: list[float] | None) -> str:
    if not interval:
        return "-"
    return f"{interval[0]:.0%}–{interval[1]:.0%}"


def _num(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _us(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} µs"
