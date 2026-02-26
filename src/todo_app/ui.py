"""Public UI entrypoints for the engagement to-do app.

This module provides a stable, concise import path for the Streamlit UI while
re-exporting the underlying implementation from :mod:`todo_app.app_ui`.
"""

from .app_ui import (  # noqa: F401
    DEADLINE_ANY,
    DEADLINE_CUSTOM,
    DEADLINE_THIS_WEEK,
    DEADLINE_TODAY,
    DEADLINE_TOMORROW,
    main,
    sidebar,
    view,
    _deadline_preset_bounds,
)

__all__ = [
    "DEADLINE_ANY",
    "DEADLINE_CUSTOM",
    "DEADLINE_THIS_WEEK",
    "DEADLINE_TODAY",
    "DEADLINE_TOMORROW",
    "_deadline_preset_bounds",
    "main",
    "sidebar",
    "view",
]

