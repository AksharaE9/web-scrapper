"""
A1 Regression Test — Packaging Contract
Asserts that every file path referenced in pyproject.toml exists in the workspace.
"""

from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

def test_pyproject_paths_exist() -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    pyproject_path = backend_dir / "pyproject.toml"
    assert pyproject_path.exists(), "backend/pyproject.toml must exist"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    # Check project.readme
    readme_ref = data.get("project", {}).get("readme")
    if readme_ref:
        readme_path = backend_dir / readme_ref
        assert readme_path.exists(), f"pyproject.toml referenced readme '{readme_ref}' which does not exist"

    # Check package paths
    packages = data.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {}).get("packages", [])
    for pkg in packages:
        pkg_path = backend_dir / pkg
        assert pkg_path.exists(), f"pyproject.toml referenced package '{pkg}' which does not exist"
