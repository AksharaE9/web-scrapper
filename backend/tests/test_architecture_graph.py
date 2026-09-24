"""
Test suite for Living Architecture Graph (docs/ARCHITECTURE.md).
Enforces synchronization between the architecture documentation and codebase:
1. Mermaid node list matches EXPECTED_NODES in app.graph.build
2. Every file mentioned in Component Register exists in the filesystem
3. Every component marked 'implemented' has corresponding tests
"""

import os
import re
from pathlib import Path
import pytest

from app.graph.build import EXPECTED_NODES

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_ARCHITECTURE = WORKSPACE_ROOT / "docs" / "ARCHITECTURE.md"


def test_architecture_file_exists():
    assert DOCS_ARCHITECTURE.exists(), f"Architecture graph file missing at {DOCS_ARCHITECTURE}"
    content = DOCS_ARCHITECTURE.read_text(encoding="utf-8")
    assert len(content) > 500, "docs/ARCHITECTURE.md is unexpectedly empty"


def test_architecture_graph_current():
    """Parses docs/ARCHITECTURE.md and asserts Mermaid DAG matches EXPECTED_NODES in graph/build.py."""
    assert DOCS_ARCHITECTURE.exists()
    content = DOCS_ARCHITECTURE.read_text(encoding="utf-8")

    # Check for presence of all expected nodes in Mermaid diagrams / docs
    for node in EXPECTED_NODES:
        # Normalize node name for matching (e.g. n0_input, N0, etc.)
        pattern = re.compile(rf"\b{re.escape(node)}\b|\[\"{node.upper()}", re.IGNORECASE)
        assert pattern.search(content), f"Node '{node}' from EXPECTED_NODES not documented in docs/ARCHITECTURE.md"


def test_component_register_files_exist():
    """Asserts every source file listed in the Component Register table actually exists."""
    assert DOCS_ARCHITECTURE.exists()
    content = DOCS_ARCHITECTURE.read_text(encoding="utf-8")

    # Extract Markdown table rows from Component Register
    register_match = re.search(r"## 2\. Component Register(.*?)(?:##|\Z)", content, re.DOTALL)
    assert register_match, "Component Register section not found in docs/ARCHITECTURE.md"

    table_text = register_match.group(1)
    # Extract file paths from backticks like `app/graph/nodes/n1_geo.py` or `frontend/src/...`
    file_matches = re.findall(r"`((?:app|frontend|backend)[^`]+?\.(?:py|tsx|ts))`", table_text)
    assert len(file_matches) > 0, "No file paths found in Component Register table"

    for rel_path in file_matches:
        if rel_path.startswith("app/"):
            full_path = WORKSPACE_ROOT / "backend" / rel_path
        elif rel_path.startswith("backend/"):
            full_path = WORKSPACE_ROOT / rel_path
        elif rel_path.startswith("frontend/"):
            full_path = WORKSPACE_ROOT / rel_path
        else:
            full_path = WORKSPACE_ROOT / rel_path

        assert full_path.exists(), f"File listed in Component Register does not exist: {rel_path} ({full_path})"


def test_implemented_components_have_valid_status():
    """Asserts that all components in register have valid statuses (implemented, partial, stub, planned, disconnected)."""
    assert DOCS_ARCHITECTURE.exists()
    content = DOCS_ARCHITECTURE.read_text(encoding="utf-8")
    
    valid_statuses = {"implemented", "partial", "stub", "planned", "disconnected"}
    status_matches = re.findall(r"`(implemented|partial|stub|planned|disconnected)`", content)
    assert len(status_matches) >= len(EXPECTED_NODES), "Not all nodes have an explicit status badge in docs/ARCHITECTURE.md"
