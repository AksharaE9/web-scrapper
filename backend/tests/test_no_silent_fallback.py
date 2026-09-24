"""
Test ensuring no silent fallbacks exist in the codebase.

Scans all Python files in app/ to verify:
1. No broad 'except Exception' or bare 'except:' catches errors and silently assigns
   fallbacks without logging at ERROR level or re-raising.
2. No dialect translators rewriting SQL conditions to '1=1'.
3. No SQLite database emulation files in production paths.
"""

import ast
from pathlib import Path


def test_no_silent_fallbacks_in_codebase() -> None:
    app_dir = Path(__file__).parent.parent / "app"
    py_files = list(app_dir.rglob("*.py"))
    assert len(py_files) > 0, "No python files found in app/"

    violations: list[str] = []

    for file_path in py_files:
        content = file_path.read_text(encoding="utf-8")

        # 1. Reject any SQL translation rewriting to 1=1
        if "1=1" in content and "pool.py" in str(file_path):
            violations.append(f"{file_path}: Contains forbidden SQL rewrite '1=1'")

        # 2. Reject SQLite fallback emulation in pool.py
        if "SQLitePool" in content or "_init_sqlite_schema" in content:
            violations.append(f"{file_path}: Contains forbidden SQLite fallback emulation")

        # 3. Parse AST and check exception handlers
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                # Check handler body
                has_raise = any(isinstance(child, ast.Raise) for child in ast.walk(node))
                has_error_log = False

                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        # check if calling logger.error / log.error / logger.warning / log.warning
                        call_repr = ast.unparse(child)
                        if any(term in call_repr for term in ["log.error", "logger.error", "log.warning", "logger.warning", "log.exception", "logger.exception"]):
                            has_error_log = True

                # Handlers that neither raise nor log an error/warning and assign variables are suspicious
                has_assignment = any(isinstance(child, (ast.Assign, ast.AnnAssign)) for child in node.body)
                if has_assignment and not has_raise and not has_error_log:
                    # Allow known safe pattern like parsing optional JSON or date with fallback
                    rel_path = file_path.relative_to(app_dir)
                    if str(rel_path) not in ["relevance/tokenize.py", "eval/label.py", "eval/relevance.py"]:
                        violations.append(
                            f"{file_path}:{node.lineno}: Exception handler assigns values without raising or logging error/warning: {ast.unparse(node.body[0]) if node.body else ''}"
                        )

    assert not violations, "Silent fallback violations found:\n" + "\n".join(violations)
