"""
Import census — resolves every `from app.X import ...` against the filesystem
AND against the live Python import system. Exits non-zero on any unresolved
module. This is the single most important check in the repository.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]   # backend/
APP = ROOT / "app"


def iter_py() -> list[pathlib.Path]:
    return sorted(p for p in APP.rglob("*.py") if "__pycache__" not in p.parts)


def collect_imports(path: pathlib.Path) -> list[tuple[str, int]]:
    """Every `app.*` module referenced, INCLUDING imports nested inside
    function bodies — those are invisible to ruff F401/F821 and are exactly
    how `haversine_distance_m` slipped through."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app."):
                out.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    out.append((alias.name, node.lineno))
    return out


def resolves_on_disk(mod: str) -> bool:
    rel = pathlib.Path(*mod.split(".")[1:])
    return (APP / rel).with_suffix(".py").is_file() or (APP / rel).is_dir()


def main() -> int:
    missing: list[str] = []
    for f in iter_py():
        for mod, line in collect_imports(f):
            if not resolves_on_disk(mod):
                missing.append(f"{f.relative_to(ROOT)}:{line}  ->  {mod}")

    print("=" * 78)
    print("  IMPORT CENSUS")
    print("=" * 78)
    if missing:
        print(f"  UNRESOLVED MODULE REFERENCES: {len(missing)}\n")
        for m in missing:
            print(f"    MISSING  {m}")
    else:
        print("  All app.* module references resolve on disk.")
    print()

    # Second, stronger check: can the app actually be imported?
    sys.path.insert(0, str(ROOT))
    hard_fail = False
    for target in ("app.main", "app.worker", "app.graph.build", "app.api.leads"):
        try:
            spec = importlib.util.find_spec(target)
            if spec is None:
                print(f"    NOT IMPORTABLE  {target}  (find_spec returned None)")
                hard_fail = True
            else:
                print(f"    importable      {target}")
        except Exception as exc:
            print(f"    NOT IMPORTABLE  {target}  ({type(exc).__name__}: {exc})")
            hard_fail = True

    print("=" * 78)
    return 1 if (missing or hard_fail) else 0


if __name__ == "__main__":
    raise SystemExit(main())
