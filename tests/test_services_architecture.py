"""Architecture tests for page-to-service boundaries."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

PAGE_FILES = [path for path in Path("src/handoff/pages").glob("*.py") if path.name != "__init__.py"]
SRC_FILES = list(Path("src/handoff").rglob("*.py"))
DEPRECATED_IMPORTS = {
    "handoff.page_models",
    "handoff.backup_schema",
    "handoff.rulebook",
}
RELOCATED_DEPENDENT_MODULES = (
    "handoff.data.io",
    "handoff.data.queries",
    "handoff.pages.now",
    "handoff.pages.projects",
    "handoff.pages.system_settings",
    "handoff.services.handoff_service",
    "handoff.services.settings_service",
)


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


def test_src_does_not_import_deprecated_top_level_core_modules() -> None:
    """Prevent reintroducing removed pre-restructure module paths."""
    offenders: list[str] = []

    for path in SRC_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module in DEPRECATED_IMPORTS:
                    offenders.append(f"{path}:{node.lineno} imports {node.module}")
                if node.module == "handoff":
                    for alias in node.names:
                        full_name = f"handoff.{alias.name}"
                        if full_name in DEPRECATED_IMPORTS:
                            offenders.append(f"{path}:{node.lineno} imports {full_name}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in DEPRECATED_IMPORTS:
                        offenders.append(f"{path}:{node.lineno} imports {alias.name}")

    assert offenders == []


def test_relocated_core_modules_remain_importable_for_core_flows() -> None:
    """Smoke-test import paths that depend on the relocated core modules."""
    for module_name in RELOCATED_DEPENDENT_MODULES:
        importlib.import_module(module_name)
