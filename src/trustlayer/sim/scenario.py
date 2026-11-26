"""Scenario files: loading them and checking them.

The format is described in scenarios/README.md. Loading fails loudly on any mistake,
because a broken scenario quietly skews every number in the report.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from trustlayer.sim import template
from trustlayer.testrange.canaries import CANARIES
from trustlayer.testrange.world import TOOL_NAMES

KINDS = ("attack", "normal")

CATEGORIES: dict[str, str] = {
    "poisoned_issue_or_email": "A poisoned issue or email",
    "hidden_web_instructions": "Hidden instructions in a web page",
    "readme_points_at_secrets": "A README that points at secrets",
    "bulk_data_allowed_channel": "Bulk data through an allowed channel",
    "data_in_url": "Data hidden in a URL",
    "retry_after_block": "Retries after a block",
    "slow_leak": "Slow leaks",
    "tool_poisoning": "Tool poisoning, rug pulls and shadowing",
}

CONDITIONS = ("leaked", "contacted", "sent", "deleted", "wrote", "answer_contains", "called")

_FIELDS = {
    "id",
    "kind",
    "category",
    "family",
    "title",
    "description",
    "prompt",
    "fixtures",
    "steps",
    "injections",
    "answer",
    "success",
    "expect",
}
_FIXTURES = {"files", "issues", "emails", "pages", "weather", "tool_descriptions"}


class ScenarioError(ValueError):
    """A scenario file is malformed."""


@dataclass(frozen=True, slots=True)
class Attempt:
    """One way of doing a step: a tool and its arguments (which may hold templates)."""

    tool: str
    args: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Step:
    """One thing the agent does. The first attempt is the plan; the rest are fallbacks
    that the agent tries, in order, if a call is refused."""

    id: str
    attempts: tuple[Attempt, ...]


@dataclass(frozen=True, slots=True)
class Injection:
    """What the attacker wants done, and the text that sets it off when the agent reads it."""

    trigger: str
    steps: tuple[Step, ...]


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    kind: str
    title: str
    prompt: str
    steps: tuple[Step, ...]
    answer: str = ""
    category: str | None = None
    family: str | None = None
    description: str = ""
    fixtures: Mapping[str, Any] = field(default_factory=dict)
    injections: tuple[Injection, ...] = ()
    success: tuple[Mapping[str, Any], ...] = ()
    expect: tuple[Mapping[str, Any], ...] = ()
    path: str = ""


def load_scenarios(root: str | Path) -> list[Scenario]:
    """Load every *.yaml file under `root`, sorted by path."""
    root = Path(root)
    paths = sorted(root.rglob("*.yaml"))
    if not paths:
        raise ScenarioError(f"no scenario files found under {root}")
    scenarios = [load_scenario(path) for path in paths]
    seen: dict[str, str] = {}
    for scenario in scenarios:
        if scenario.id in seen:
            raise ScenarioError(
                f"duplicate id {scenario.id!r} in {scenario.path} and {seen[scenario.id]}"
            )
        seen[scenario.id] = scenario.path
    return scenarios


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioError(f"{path}: not valid YAML: {exc}") from exc
    try:
        return _parse(data, path)
    except ScenarioError as exc:
        raise ScenarioError(f"{path}: {exc}") from None


def _parse(data: Any, path: Path) -> Scenario:
    if not isinstance(data, dict):
        raise ScenarioError("the file must hold a mapping of fields")
    unknown = set(data) - _FIELDS
    if unknown:
        raise ScenarioError(f"unknown field(s): {', '.join(sorted(unknown))}")

    scenario_id = _text(data, "id")
    if scenario_id != path.stem:
        raise ScenarioError(f"id {scenario_id!r} must match the file name {path.stem!r}")
    kind = _text(data, "kind")
    if kind not in KINDS:
        raise ScenarioError(f"kind must be one of: {', '.join(KINDS)}")

    steps = _steps(data.get("steps"), "steps")
    injections = tuple(
        _injection(item, f"injections[{i}]") for i, item in enumerate(_list(data, "injections"))
    )
    success = _conditions(data.get("success"), "success")
    expect = _conditions(data.get("expect"), "expect")
    category = data.get("category")
    family = data.get("family")

    if kind == "attack":
        if category not in CATEGORIES:
            raise ScenarioError(f"category must be one of: {', '.join(CATEGORIES)}")
        if not isinstance(family, str) or not family:
            raise ScenarioError("an attack needs a family, used later to split train and test sets")
        if not injections:
            raise ScenarioError("an attack needs at least one injection")
        if not success:
            raise ScenarioError("an attack needs success conditions")
        if expect:
            raise ScenarioError("an attack uses 'success', not 'expect'")
    else:
        if category or family or injections or success:
            raise ScenarioError("a normal task has no category, family, injections or success")
        if not expect:
            raise ScenarioError("a normal task needs expect conditions")

    fixtures = data.get("fixtures") or {}
    _check_fixtures(fixtures)

    scenario = Scenario(
        id=scenario_id,
        kind=kind,
        title=_text(data, "title"),
        prompt=_text(data, "prompt"),
        steps=steps,
        answer=str(data.get("answer") or ""),
        category=category,
        family=family,
        description=str(data.get("description") or "").strip(),
        fixtures=fixtures,
        injections=injections,
        success=success,
        expect=expect,
        path=str(path),
    )
    _check_refs(scenario)
    return scenario


def _text(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ScenarioError(f"{key!r} is required and must be text")
    return value.strip()


def _list(data: Mapping[str, Any], key: str) -> list[Any]:
    value = data.get(key) or []
    if not isinstance(value, list):
        raise ScenarioError(f"{key!r} must be a list")
    return value


def _steps(raw: Any, where: str) -> tuple[Step, ...]:
    if not isinstance(raw, list) or not raw:
        raise ScenarioError(f"{where} must be a non-empty list")
    return tuple(_step(item, f"{where}[{i}]") for i, item in enumerate(raw))


def _step(raw: Any, where: str) -> Step:
    if not isinstance(raw, dict):
        raise ScenarioError(f"{where} must be a mapping with id, tool and args")
    unknown = set(raw) - {"id", "tool", "args", "fallbacks"}
    if unknown:
        raise ScenarioError(f"{where}: unknown field(s): {', '.join(sorted(unknown))}")
    step_id = raw.get("id")
    if not isinstance(step_id, str) or not step_id:
        raise ScenarioError(f"{where} needs an id")
    attempts = [_attempt(raw, where)]
    fallbacks = raw.get("fallbacks") or []
    if not isinstance(fallbacks, list):
        raise ScenarioError(f"{where}.fallbacks must be a list")
    for j, fallback in enumerate(fallbacks):
        label = f"{where}.fallbacks[{j}]"
        if not isinstance(fallback, dict) or set(fallback) - {"tool", "args"}:
            raise ScenarioError(f"{label} takes only tool and args")
        attempts.append(_attempt(fallback, label))
    return Step(id=step_id, attempts=tuple(attempts))


def _attempt(raw: Mapping[str, Any], where: str) -> Attempt:
    tool = raw.get("tool")
    if tool not in TOOL_NAMES:
        raise ScenarioError(
            f"{where}: unknown tool {tool!r}; use one of: {', '.join(sorted(TOOL_NAMES))}"
        )
    args = raw.get("args") or {}
    if not isinstance(args, dict):
        raise ScenarioError(f"{where}: args must be a mapping")
    return Attempt(tool=tool, args=args)


def _injection(raw: Any, where: str) -> Injection:
    if not isinstance(raw, dict) or set(raw) - {"trigger", "steps"}:
        raise ScenarioError(f"{where} takes only trigger and steps")
    trigger = raw.get("trigger")
    if not isinstance(trigger, str) or not trigger.strip():
        raise ScenarioError(
            f"{where} needs a trigger: text from the attack that the agent will read"
        )
    return Injection(trigger=trigger, steps=_steps(raw.get("steps"), f"{where}.steps"))


def _conditions(raw: Any, where: str) -> tuple[Mapping[str, Any], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ScenarioError(f"{where} must be a list")
    parsed = []
    for i, item in enumerate(raw):
        label = f"{where}[{i}]"
        if not isinstance(item, dict) or len(item) != 1:
            raise ScenarioError(f"{label} must hold exactly one condition, like '- leaked: any'")
        name, value = next(iter(item.items()))
        _check_condition(name, value, label)
        parsed.append({name: value})
    return tuple(parsed)


def _check_condition(name: str, value: Any, label: str) -> None:
    if name == "leaked":
        if value != "any" and value not in CANARIES:
            raise ScenarioError(f"{label}: leaked must be 'any' or one of: {', '.join(CANARIES)}")
    elif name in ("contacted", "deleted", "answer_contains"):
        if not isinstance(value, str) or not value:
            raise ScenarioError(f"{label}: {name} needs text")
    elif name == "called":
        if value not in TOOL_NAMES:
            raise ScenarioError(f"{label}: unknown tool {value!r}")
    elif name in ("sent", "wrote"):
        key = "to" if name == "sent" else "path"
        if not isinstance(value, dict) or not isinstance(value.get(key), str):
            raise ScenarioError(f"{label}: {name} needs {key!r}")
        if set(value) - {key, "contains"} or not isinstance(value.get("contains", ""), str):
            raise ScenarioError(f"{label}: {name} takes {key!r} and an optional 'contains' text")
    else:
        raise ScenarioError(
            f"{label}: unknown condition {name!r}; use one of: {', '.join(CONDITIONS)}"
        )


def _check_fixtures(fixtures: Any) -> None:
    if not isinstance(fixtures, dict):
        raise ScenarioError("fixtures must be a mapping")
    unknown = set(fixtures) - _FIXTURES
    if unknown:
        raise ScenarioError(f"unknown fixture(s): {', '.join(sorted(unknown))}")
    for key in ("files", "pages", "weather", "tool_descriptions"):
        if not isinstance(fixtures.get(key) or {}, dict):
            raise ScenarioError(f"fixtures.{key} must be a mapping")
    for name in fixtures.get("tool_descriptions") or {}:
        if name not in TOOL_NAMES:
            raise ScenarioError(f"fixtures.tool_descriptions: unknown tool {name!r}")
    needed = {"issues": ("id", "title", "body"), "emails": ("id", "from", "subject", "body")}
    for key, keys in needed.items():
        items = fixtures.get(key) or []
        if not isinstance(items, list):
            raise ScenarioError(f"fixtures.{key} must be a list")
        for item in items:
            if not isinstance(item, dict) or any(k not in item for k in keys):
                raise ScenarioError(f"each item in fixtures.{key} needs: {', '.join(keys)}")


def _check_refs(scenario: Scenario) -> None:
    all_steps = list(scenario.steps) + [s for inj in scenario.injections for s in inj.steps]
    ids = [step.id for step in all_steps]
    repeated = sorted({step_id for step_id in ids if ids.count(step_id) > 1})
    if repeated:
        raise ScenarioError(f"step ids must be unique; repeated: {', '.join(repeated)}")
    known = set(ids)
    texts = [scenario.answer]
    for step in all_steps:
        for attempt in step.attempts:
            texts.extend(_strings(attempt.args))
    for text in texts:
        try:
            missing = [ref for ref in template.refs(text) if ref not in known]
        except template.TemplateError as exc:
            raise ScenarioError(str(exc)) from exc
        if missing:
            raise ScenarioError(f"a template refers to unknown step(s): {', '.join(missing)}")


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in _strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in _strings(item)]
    return []
