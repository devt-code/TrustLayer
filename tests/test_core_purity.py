"""The core stays pure: standard library and NumPy only, and no I/O of any kind.

This reads the core's source code instead of importing it, so a forbidden import can't
hide behind a lazy import or an `if`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[1] / "src" / "trustlayer" / "core"

# Standard-library modules that do I/O or read the outside world: the network, files,
# processes, the clock, randomness, the environment. The shell passes such things in.
FORBIDDEN_STDLIB = {
    "asyncio", "concurrent", "ctypes", "dbm", "fileinput", "ftplib", "glob", "http",
    "imaplib", "io", "logging", "mmap", "multiprocessing", "os", "pathlib", "pickle",
    "poplib", "random", "secrets", "select", "selectors", "shelve", "shutil", "signal",
    "smtplib", "socket", "socketserver", "sqlite3", "ssl", "subprocess", "sys", "tempfile",
    "threading", "time", "urllib", "uuid", "webbrowser", "xmlrpc", "zipfile",
}  # fmt: skip
ALLOWED_THIRD_PARTY = {"numpy"}
FORBIDDEN_CALLS = {"open", "print", "input", "eval", "exec", "compile", "__import__", "breakpoint"}


def _core_files() -> list[Path]:
    files = sorted(CORE.rglob("*.py"))
    assert files, f"no Python files found in {CORE}"
    return files


def _imported_modules(tree: ast.AST) -> list[str]:
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
    return modules


def _problem(module: str) -> str | None:
    """Why the core may not import `module`, or None if it may."""
    if module == "trustlayer.core" or module.startswith("trustlayer.core."):
        return None
    top = module.split(".")[0]
    if top in ALLOWED_THIRD_PARTY:
        return None
    if top not in sys.stdlib_module_names and top != "__future__":
        return "it is not the standard library or NumPy"
    if top in FORBIDDEN_STDLIB:
        return "it does I/O or reads the outside world"
    return None


@pytest.mark.parametrize("path", _core_files(), ids=lambda p: p.name)
def test_core_imports_only_allowed_modules(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for module in _imported_modules(tree):
        problem = _problem(module)
        assert problem is None, f"{path.name} imports {module}, but {problem}"


@pytest.mark.parametrize("path", _core_files(), ids=lambda p: p.name)
def test_core_never_calls_io_builtins(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            assert name not in FORBIDDEN_CALLS, f"{path.name}:{node.lineno} calls {name}()"


def test_the_checker_catches_bad_imports() -> None:
    tree = ast.parse("import socket\nfrom trustlayer.sim import runner\nimport requests\n")
    modules = _imported_modules(tree)
    assert modules == ["socket", "trustlayer.sim", "requests"]
    assert all(_problem(module) for module in modules)
    assert _problem("dataclasses") is None
    assert _problem("numpy.linalg") is None
    assert _problem("trustlayer.core.events") is None
