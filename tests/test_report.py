"""Metrics, the results file and the results page."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trustlayer.cli import main
from trustlayer.eval.metrics import percentile, wilson_interval
from trustlayer.eval.report import evaluate, format_summary
from trustlayer.eval.site import render_page
from trustlayer.sim.scenario import load_scenarios
from trustlayer.testrange.canaries import CANARIES

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


@pytest.fixture(scope="module")
def results() -> dict:
    return evaluate(load_scenarios(SCENARIOS))


def test_wilson_interval_known_values() -> None:
    low, high = wilson_interval(10, 10)
    assert round(low, 3) == 0.722 and high == 1.0
    low, high = wilson_interval(0, 40)
    assert low == 0.0 and round(high, 3) == 0.088
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_percentile_nearest_rank() -> None:
    assert percentile([], 95) is None
    assert percentile([5, 1, 3], 50) == 3
    assert percentile(list(range(1, 101)), 95) == 95


def test_results_have_both_rows_and_the_baseline_numbers(results: dict) -> None:
    assert [row["name"] for row in results["rows"]] == ["no-gateway", "trustlayer"]
    for row in results["rows"]:
        summary = row["summary"]
        assert summary["attack_success_rate"] == 1.0
        assert summary["normal_completion_rate"] == 1.0
        assert summary["prompts_per_normal_task"] == 0.0
    assert results["rows"][0]["summary"]["core_us_p95"] is None
    assert results["rows"][1]["summary"]["core_us_p95"] is not None


def test_results_never_hold_a_canary_in_plain_text(results: dict) -> None:
    text = json.dumps(results)
    assert not any(value in text for value in CANARIES.values())
    assert "[canary:" in text


def test_summary_and_page(results: dict) -> None:
    assert "Attacks that worked" in format_summary(results)
    page = render_page(results)
    assert page.startswith("<!doctype html>")
    assert "<script" not in page.lower()


def test_page_escapes_text_from_scenarios(results: dict) -> None:
    hostile = json.loads(json.dumps(results))
    hostile["rows"][0]["scenarios"][0]["title"] = "<script>alert(1)</script>"
    page = render_page(hostile)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_cli_writes_results_and_page(tmp_path: Path) -> None:
    out = tmp_path / "results.json"
    assert main(["eval", "--scenarios", str(SCENARIOS), "--out", str(out)]) == 0
    assert main(["site", "--results", str(out), "--out", str(tmp_path / "site")]) == 0
    assert (tmp_path / "site" / "index.html").exists()
    assert (tmp_path / "site" / "results.json").exists()
