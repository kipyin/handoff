"""Shared filesystem path helpers for the application."""

from __future__ import annotations

from pathlib import Path


def get_app_root() -> Path:
    """Return the root directory where ``app.py`` and ``src/`` live."""
    return Path(__file__).resolve().parents[3]
