"""Main entrypoint for the Handoff app.

This file intentionally exposes a stable APP_VERSION constant so an updater can
read it, while delegating UI rendering to handoff.ui and
Streamlit's st.navigation API.
"""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from handoff.pages.analytics import render_analytics_page
from handoff.pages.docs import render_docs_page
from handoff.pages.projects import render_projects_page
from handoff.pages.settings import render_settings_page
from handoff.pages.todos import render_todos_page
from handoff.ui import setup
from handoff.version import __version__ as APP_VERSION


def _page(renderer: Callable[[], None]) -> Callable[[], None]:
    """Wrap a page renderer so global setup runs first."""

    def _run() -> None:
        setup(APP_VERSION)
        renderer()

    _run.__name__ = renderer.__name__
    return _run


def main() -> None:
    """Run the Handoff app using the Streamlit navigation API."""
    pages = [
        st.Page(_page(render_todos_page), title="Todos", icon="✅"),
        st.Page(_page(render_projects_page), title="Projects", icon="📁"),
        st.Page(_page(render_analytics_page), title="Dashboard", icon="📊"),
        st.Page(_page(render_settings_page), title="Settings", icon="⚙️"),
        st.Page(_page(render_docs_page), title="Docs", icon="📖"),
    ]
    nav = st.navigation(pages, position="top")
    nav.run()


if __name__ == "__main__":
    main()
