"""Fail-closed static audit of registered aiogram slash-command handlers.

Scans every application Python module (not only the two currently known files).
Unknown command-filter forms must be explicitly reviewed rather than silently
treated as a clean catalog.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


EXCLUDED_DIRS = {"tests", "scripts", "docs", "deploy", ".github", ".venv", "venv", "__pycache__"}
COMMAND_NAMES = {"Command", "CommandStart"}


def _literal_commands(node: ast.Call) -> tuple[str, ...]:
    if node.keywords:
        raise ValueError("Keyword/dynamic Command arguments need catalog audit review")
    names: list[str] = []
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            names.append(arg.value)
        elif isinstance(arg, (ast.List, ast.Tuple)):
            for element in arg.elts:
                if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                    raise ValueError("Dynamic slash command inside command collection")
                names.append(element.value)
        else:
            raise ValueError("Dynamic slash-command registration")
    if not names:
        raise ValueError("Empty Command() registration")
    return tuple(names)


def _filter_calls(expr: ast.AST) -> Iterable[ast.Call]:
    for node in ast.walk(expr):
        if isinstance(node, ast.Call):
            yield node


def scan_module(path: Path) -> set[tuple[str, str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases: dict[str, str] = {}
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in {"aiogram.filters", "aiogram.filters.command"}:
            for name in node.names:
                if name.name in COMMAND_NAMES:
                    aliases[name.asname or name.name] = name.name
        elif isinstance(node, ast.Import):
            for entry in node.names:
                if entry.name in {"aiogram.filters", "aiogram.filters.command"}:
                    modules.add(entry.asname or entry.name)
    found: set[tuple[str, str, str]] = set()
    for handler in ast.walk(tree):
        if not isinstance(handler, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for decorator in handler.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr != "message":
                continue
            for call in _filter_calls(decorator):
                canonical = ""
                if isinstance(call.func, ast.Name):
                    canonical = aliases.get(call.func.id, "")
                    if not canonical and call.func.id in COMMAND_NAMES:
                        raise ValueError(f"{path}:{call.lineno}: undeclared command filter {call.func.id}")
                elif isinstance(call.func, ast.Attribute) and call.func.attr in COMMAND_NAMES:
                    root = ast.unparse(call.func.value)
                    if root in modules or root in {"aiogram.filters", "aiogram.filters.command"}:
                        canonical = call.func.attr
                    else:
                        raise ValueError(f"{path}:{call.lineno}: unrecognized command filter source")
                if not canonical:
                    continue
                if canonical == "CommandStart":
                    if call.args or call.keywords:
                        raise ValueError(f"{path}:{call.lineno}: CommandStart options require review")
                    names = ("start",)
                else:
                    names = _literal_commands(call)
                for name in names:
                    if not name.isascii() or not name.islower() or not name.isidentifier():
                        raise ValueError(f"{path}:{call.lineno}: invalid command {name}")
                    found.add((name, path.name, handler.name))
    return found


def scan_repository(root: Path) -> set[tuple[str, str, str]]:
    entries: set[tuple[str, str, str]] = set()
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIRS or part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue
        entries.update(scan_module(path))
    return entries


def check_catalog(root: Path) -> None:
    import sys
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from telegram_commands import COMMANDS, validate_catalog
    validate_catalog()
    actual = scan_repository(root)
    expected = {(x.name, x.source, x.handler) for x in COMMANDS}
    if actual != expected:
        missing = sorted(actual - expected)
        obsolete = sorted(expected - actual)
        raise ValueError(f"Slash handler/catalog drift: unlisted={missing}; stale={obsolete}")


if __name__ == "__main__":
    try:
        check_catalog(Path(__file__).resolve().parents[1])
    except (ValueError, SyntaxError) as exc:
        raise SystemExit(f"Telegram command catalog FAIL: {exc}")
    print("Telegram command catalog PASS")
