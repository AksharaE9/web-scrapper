"""
AST and Dynamic Import Integrity Test Suite

Enforces:
1. Every Python module in `app/` is cleanly importable at top-level.
2. Every `from app.X import Y` symbol reference resolves to an actual exported attribute or submodule.
3. No lazy/inline first-party imports reside inside function or method bodies without explicit justification.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "app"


def get_all_app_python_files() -> list[Path]:
    """Return all .py files in app/."""
    return sorted([p for p in APP_DIR.rglob("*.py") if not p.name.startswith("__pycache__")])


def test_all_modules_importable() -> None:
    """Recursively import every module in app/ to detect circular dependencies or missing top-level symbols."""
    failures: list[str] = []
    for py_file in get_all_app_python_files():
        rel = py_file.relative_to(APP_DIR.parent)
        mod_name = ".".join(rel.with_suffix("").parts)
        try:
            importlib.import_module(mod_name)
        except Exception as exc:
            failures.append(f"{mod_name} ({py_file}): {exc}")

    assert not failures, f"The following modules failed to import:\n" + "\n".join(failures)


def test_ast_symbol_resolution() -> None:
    """
    Parse every .py file using AST, extract every `from app.X import Y` statement,
    and verify symbol Y actually exists on module app.X or is an importable submodule.
    """
    unresolved_symbols: list[str] = []

    for py_file in get_all_app_python_files():
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {py_file}: {e}")

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
                mod_name = node.module
                try:
                    mod = importlib.import_module(mod_name)
                except Exception as exc:
                    unresolved_symbols.append(
                        f"{py_file.name}:{node.lineno} -> Module '{mod_name}' failed to import: {exc}"
                    )
                    continue

                for alias in node.names:
                    symbol_name = alias.name
                    if symbol_name == "*":
                        continue
                    if not hasattr(mod, symbol_name):
                        # Symbol might be a submodule
                        submod_name = f"{mod_name}.{symbol_name}"
                        try:
                            importlib.import_module(submod_name)
                        except Exception:
                            unresolved_symbols.append(
                                f"{py_file.name}:{node.lineno} -> Symbol '{symbol_name}' not found in module '{mod_name}'"
                            )

    assert not unresolved_symbols, "Found unresolved first-party import symbols:\n" + "\n".join(unresolved_symbols)


def test_no_unapproved_lazy_first_party_imports() -> None:
    """
    Assert no first-party imports (`from app.X import Y` or `import app.X`) reside inside function bodies,
    except where an explicit '# allowed-lazy-import: reason' comment is provided.
    """
    unapproved_lazy: list[str] = []

    for py_file in get_all_app_python_files():
        source = py_file.read_text(encoding="utf-8")
        lines = source.splitlines()
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if child is node:
                        continue
                    if isinstance(child, ast.ImportFrom) and child.module and child.module.startswith("app"):
                        line_content = lines[child.lineno - 1] if child.lineno <= len(lines) else ""
                        if "allowed-lazy-import" not in line_content:
                            unapproved_lazy.append(
                                f"{py_file.relative_to(APP_DIR.parent)}:{child.lineno} in '{node.name}': from {child.module} import ..."
                            )
                    elif isinstance(child, ast.Import):
                        for alias in child.names:
                            if alias.name.startswith("app"):
                                line_content = lines[child.lineno - 1] if child.lineno <= len(lines) else ""
                                if "allowed-lazy-import" not in line_content:
                                    unapproved_lazy.append(
                                        f"{py_file.relative_to(APP_DIR.parent)}:{child.lineno} in '{node.name}': import {alias.name}"
                                    )

    assert not unapproved_lazy, (
        "Found unapproved lazy first-party imports inside function bodies:\n"
        + "\n".join(unapproved_lazy)
        + "\n\nHoist them to module scope or add '# allowed-lazy-import: <reason>'."
    )
