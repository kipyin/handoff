"""Architecture tests for page-to-service boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

PAGE_FILES = [
    Path("src/handoff/pages/dashboard.py"),
    Path("src/handoff/pages/projects.py"),
    Path("src/handoff/pages/settings.py"),
    Path("src/handoff/pages/todos.py"),
]


def test_pages_do_not_import_data_layer_directly() -> None:
    """Pages should go through services rather than importing `handoff.data`."""
    offenders: list[str] = []

    for path in PAGE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "handoff.data":
                offenders.append(f"{path}:{node.lineno}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "handoff.data":
                        offenders.append(f"{path}:{node.lineno}")

    assert offenders == []
