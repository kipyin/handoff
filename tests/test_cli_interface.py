"""Regression tests for the new CLI interface stub."""

from __future__ import annotations

import importlib
import pytest

import handoff.interfaces.cli as cli_module


def test_run_cli_raises_not_implemented_error() -> None:
    """run_cli() should raise NotImplementedError with a helpful message."""
    with pytest.raises(NotImplementedError) as exc_info:
        cli_module.run_cli()

    assert "not yet implemented" in str(exc_info.value).lower()
    assert "streamlit" in str(exc_info.value).lower()


def test_cli_module_exports_run_cli() -> None:
    """The CLI interface module should export run_cli via __all__."""
    assert "run_cli" in cli_module.__all__
    assert cli_module.run_cli is not None


def test_cli_interface_is_importable() -> None:
    """The new CLI interface module should be importable."""
    imported = importlib.import_module("handoff.interfaces.cli")
    assert hasattr(imported, "run_cli")


def test_cli_interface_is_reloadable() -> None:
    """The CLI interface module should be safely reloadable."""
    before_all = set(cli_module.__all__)
    reloaded = importlib.reload(cli_module)

    assert hasattr(reloaded, "run_cli")
    assert set(reloaded.__all__) == before_all
