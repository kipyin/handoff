"""Startup, config, paths, and logging for the Handoff app."""

from .docs import get_readme_intro, read_markdown_from_app_root
from .logging import configure_logging, log_application_action
from .paths import get_app_root

__all__ = [
    "configure_logging",
    "get_app_root",
    "get_readme_intro",
    "log_application_action",
    "read_markdown_from_app_root",
]
