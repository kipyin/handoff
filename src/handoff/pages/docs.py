"""Docs page for rendering README and RELEASE_NOTES inside the app."""

from __future__ import annotations

import streamlit as st

from handoff.docs import read_markdown_from_app_root
from handoff.version import __version__ as APP_VERSION


def render_docs_page() -> None:
    """Render README and release notes as markdown inside the app."""
    st.subheader(f"Documentation ({APP_VERSION})")

    readme_text = read_markdown_from_app_root("README.md")
    release_notes_text = read_markdown_from_app_root("RELEASE_NOTES.md")

    readme_tab, notes_tab = st.tabs(["README", "Release notes"])

    with readme_tab:
        st.markdown(readme_text)

    with notes_tab:
        st.markdown(release_notes_text)
