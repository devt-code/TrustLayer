"""Tiny templates for the scripted agent's steps.

`{{ env }}` is replaced with the text the agent got back from the step whose id is `env`.
Filters change that text, applied left to right:

    {{ env | b64 }}          base64-encode it
    {{ env | url }}          percent-encode it, for use inside a URL
    {{ env | slice:0:8 }}    keep characters 0 to 8, like Python's text[0:8]

A step that has not run yet counts as empty text.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import quote

_PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}")


class TemplateError(ValueError):
    """A placeholder is empty, or uses a filter wrongly."""


def refs(text: str) -> list[str]:
    """The step ids that a template refers to, in order. Checks the filters too."""
    return [_parse(match.group(1))[0] for match in _PLACEHOLDER.finditer(text)]


def render(text: str, results: Mapping[str, str]) -> str:
    """Fill in every placeholder in `text`."""

    def fill(match: re.Match[str]) -> str:
        ref, filters = _parse(match.group(1))
        value = results.get(ref, "")
        for name, args in filters:
            value = _FILTERS[name](value, args)
        return value

    return _PLACEHOLDER.sub(fill, text)


def render_value(value: Any, results: Mapping[str, str]) -> Any:
    """Like `render`, for every string inside nested lists and dicts."""
    if isinstance(value, str):
        return render(value, results)
    if isinstance(value, list):
        return [render_value(item, results) for item in value]
    if isinstance(value, dict):
        return {key: render_value(item, results) for key, item in value.items()}
    return value


def _parse(inner: str) -> tuple[str, list[tuple[str, list[str]]]]:
    parts = [part.strip() for part in inner.split("|")]
    ref = parts[0]
    if not ref:
        raise TemplateError("a placeholder needs a step id, like {{ env }}")
    filters = []
    for part in parts[1:]:
        name, *args = part.split(":")
        if name not in _FILTERS:
            raise TemplateError(f"unknown filter {name!r}; use one of: {', '.join(_FILTERS)}")
        _FILTERS[name]("", args)  # fail now, not mid-run, on bad arguments
        filters.append((name, args))
    return ref, filters


def _b64(value: str, args: list[str]) -> str:
    if args:
        raise TemplateError("b64 takes no arguments")
    return base64.b64encode(value.encode()).decode()


def _url(value: str, args: list[str]) -> str:
    if args:
        raise TemplateError("url takes no arguments")
    return quote(value, safe="")


def _slice(value: str, args: list[str]) -> str:
    if len(args) not in (1, 2):
        raise TemplateError("slice needs bounds, like slice:0:8")
    try:
        start = int(args[0]) if args[0] else None
        stop = int(args[1]) if len(args) == 2 and args[1] else None
    except ValueError as exc:
        raise TemplateError(f"slice bounds must be whole numbers, not {args}") from exc
    return value[start:stop]


_FILTERS: dict[str, Callable[[str, list[str]], str]] = {
    "b64": _b64,
    "url": _url,
    "slice": _slice,
}
