"""
Route surface alignment audit.
Compares FastAPI defined routes vs frontend called endpoints.
Exits non-zero if any frontend endpoint is called but not defined in FastAPI.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]       # backend/
FRONTEND_SRC = ROOT.parent / "frontend" / "src"

sys.path.insert(0, str(ROOT))
from app.main import app


def get_defined_routes() -> list[str]:
    """Extract all OpenAPI path definitions from FastAPI app."""
    openapi_schema = app.openapi()
    return sorted(openapi_schema.get("paths", {}).keys())


def route_to_regex(route: str) -> re.Pattern:
    """Convert an OpenAPI route like /api/runs/{run_id}/leads to a regex ^/api/runs/[^/]+/leads$"""
    escaped = re.escape(route)
    pattern = re.sub(r"\\\{[a-zA-Z0-9_]+\\\}", r"([^/]+)", escaped)
    return re.compile(f"^{pattern}$")


def get_called_routes() -> set[str]:
    """Scan frontend files for API endpoint strings/templates."""
    called = set()
    if not FRONTEND_SRC.exists():
        print(f"Warning: Frontend source path {FRONTEND_SRC} does not exist.")
        return called

    # Pattern matching API calls: fetch(`${BASE_URL}/api/...`), http.get("*/api/..."), `/api/...`
    # Exclude import statements like: import ... from ".../api/client"
    url_pattern = re.compile(r"(?:\$\{BASE_URL\}|\*)?(/api/[a-zA-Z0-9_\-\$\{\}/:]+)", re.MULTILINE)
    import_pattern = re.compile(r"(?:import|from)\s+['\"`][^'\"`]*['\"`]")

    for p in FRONTEND_SRC.rglob("*"):
        if p.suffix in (".ts", ".tsx", ".js", ".jsx") and "node_modules" not in p.parts:
            text = p.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                line_str = line.strip()
                if line_str.startswith("import ") or line_str.startswith("export * from") or line_str.startswith("export {"):
                    continue
                for match in url_pattern.finditer(line):
                    raw_path = match.group(1)
                    # Exclude module import paths like /api/client
                    if raw_path.endswith("/api/client") or raw_path.endswith("/api/types"):
                        continue
                    clean = raw_path.split("?")[0].rstrip("/")
                    clean = re.sub(r"\$\{([^}]+)\}", r"__PARAM__", clean)
                    clean = re.sub(r":([a-zA-Z0-9_]+)", r"__PARAM__", clean)
                    if clean and clean != "/api":
                        called.add(clean)

    return called


def main() -> int:
    defined_routes = get_defined_routes()
    called_routes = get_called_routes()

    defined_patterns = [(r, route_to_regex(r)) for r in defined_routes]

    matched_called = set()
    unmatched_called = []

    for called in sorted(called_routes):
        test_path = called.replace("__PARAM__", "testparam")
        found = False
        for def_route, pattern in defined_patterns:
            if pattern.match(test_path) or pattern.match(called):
                matched_called.add(def_route)
                found = True
                break
        if not found:
            unmatched_called.append(called)

    defined_uncalled = [r for r in defined_routes if r not in matched_called]

    print("=" * 78)
    print("  ROUTE SURFACE ALIGNMENT AUDIT")
    print("=" * 78)

    print(f"\n[ MATCHED ROUTES: {len(matched_called)} ]")
    for r in sorted(matched_called):
        print(f"  OK   {r}")

    print(f"\n[ DEFINED BUT NOT CALLED BY FRONTEND (INFO/ADMIN/SPECIALIZED): {len(defined_uncalled)} ]")
    for r in sorted(defined_uncalled):
        print(f"  INFO {r}")

    if unmatched_called:
        print(f"\n[ CALLED BUT NOT DEFINED (FATAL): {len(unmatched_called)} ]")
        for r in unmatched_called:
            print(f"  FAIL {r}")
        print("\n" + "=" * 78)
        return 1
    else:
        print("\n[ CALLED BUT NOT DEFINED: 0 ]")
        print("  All frontend API calls match defined backend routes.")
        print("=" * 78)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
