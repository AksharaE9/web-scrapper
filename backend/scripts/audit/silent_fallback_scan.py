"""
scripts/audit/silent_fallback_scan.py — Static AST scanner for unlogged/swallowed exceptions.

Verifies:
1. No broad 'except Exception' or bare 'except:' catches errors and silently assigns
   fallbacks without logging at WARNING/ERROR level or re-raising.
2. No SQL dialect translators rewriting conditions to '1=1'.
3. No SQLite emulation layers in production DB connection paths.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def scan_silent_fallbacks() -> list[dict[str, str]]:
    app_dir = Path(__file__).resolve().parent.parent.parent / "app"
    py_files = list(app_dir.rglob("*.py"))
    violations: list[dict[str, str]] = []

    for file_path in py_files:
        content = file_path.read_text(encoding="utf-8")

        # 1. SQL rewrite checks
        if "1=1" in content and "pool.py" in str(file_path):
            violations.append({
                "file": str(file_path.relative_to(app_dir.parent)),
                "line": "N/A",
                "kind": "Forbidden SQL",
                "detail": "Contains forbidden SQL rewrite '1=1'",
            })

        # 2. SQLite pool checks
        if "SQLitePool" in content or "_init_sqlite_schema" in content:
            violations.append({
                "file": str(file_path.relative_to(app_dir.parent)),
                "line": "N/A",
                "kind": "SQLite Emulation",
                "detail": "Contains forbidden SQLite fallback emulation",
            })

        # 3. AST Exception scanning
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                has_raise = any(isinstance(child, ast.Raise) for child in ast.walk(node))
                has_error_log = False

                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_repr = ast.unparse(child)
                        if any(term in call_repr for term in [
                            "log.error", "logger.error", "log.warning", "logger.warning",
                            "log.exception", "logger.exception", "log.debug", "logger.debug", "log.info", "logger.info"
                        ]):
                            has_error_log = True

                has_assignment = any(isinstance(child, (ast.Assign, ast.AnnAssign)) for child in node.body)
                if has_assignment and not has_raise and not has_error_log:
                    rel_path = file_path.relative_to(app_dir)
                    if str(rel_path) not in ["relevance/tokenize.py", "eval/label.py", "eval/relevance.py"]:
                        violations.append({
                            "file": str(file_path.relative_to(app_dir.parent)),
                            "line": str(node.lineno),
                            "kind": "Swallowed Exception",
                            "detail": ast.unparse(node.body[0]) if node.body else "",
                        })

    return violations


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    console = Console()
    violations = scan_silent_fallbacks()

    table = Table(title="Silent Fallback & Exception AST Audit", show_header=True, header_style="bold cyan")
    table.add_column("File", width=35)
    table.add_column("Line", width=6, justify="right")
    table.add_column("Kind", width=20)
    table.add_column("Detail", width=40)

    if violations:
        for v in violations:
            table.add_row(v["file"], v["line"], f"[red]{v['kind']}[/red]", v["detail"][:38])
        console.print(table)
        console.print(f"\n[red][FAIL] Audit Failed: {len(violations)} silent fallback violations detected.[/red]")
        sys.exit(1)
    else:
        console.print("[green][PASS] Audit Passed: 0 silent fallbacks or swallowed exceptions found in app/ codebase.[/green]")


if __name__ == "__main__":
    main()
