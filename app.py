"""Main entrypoint for the Handoff app.

This file intentionally exposes a stable APP_VERSION constant so an updater can
read it, while delegating UI rendering to handoff.ui and
Streamlit's st.navigation API.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

import streamlit as st

from handoff.interfaces.streamlit.pages.now import render_now_page
from handoff.interfaces.streamlit.ui import (
    render_about_page,
    render_dashboard_page,
    render_projects_page,
    render_system_settings_page,
    setup,
)
from handoff.version import __version__ as APP_VERSION


def _page(renderer: Callable[[], None]) -> Callable[[], None]:
    """Wrap a page renderer so global setup runs first."""

    @wraps(renderer)
    def _run() -> None:
        setup(APP_VERSION)
        renderer()

    return _run


def main() -> None:
    """Run the Handoff app using the Streamlit navigation API."""
    pages = {
        "": [
            st.Page(_page(render_now_page), title="Now", icon="🎯"),
            st.Page(_page(render_dashboard_page), title="Dashboard", icon="📊"),
        ],
        "Settings": [
            st.Page(_page(render_projects_page), title="Projects", icon="📁"),
            st.Page(_page(render_about_page), title="About", icon="📖"),
            st.Page(_page(render_system_settings_page), title="System Settings", icon="⚙️"),
        ],
    }
    nav = st.navigation(pages, position="top")
    nav.run()


if __name__ == "__main__":
    main()
