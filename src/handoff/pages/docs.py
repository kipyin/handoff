"""Docs page for rendering README and RELEASE_NOTES inside the app."""

from __future__ import annotations

import streamlit as st

from handoff.docs import read_markdown_from_app_root
from handoff.version import __version__ as APP_VERSION


def _cached_markdown(name: str) -> str:
    """Return markdown content from app root, cached in session state to avoid repeated file I/O."""
    cache_key = "_docs_md_cache"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = {}
    cache = st.session_state[cache_key]
    if name not in cache:
        cache[name] = read_markdown_from_app_root(name)
    return cache[name]


def render_docs_page() -> None:
    """Render README and release notes as markdown inside the app."""
    st.subheader(f"Documentation ({APP_VERSION})")

    readme_text = _cached_markdown("README.md")
    release_notes_text = _cached_markdown("RELEASE_NOTES.md")

    readme_tab, notes_tab = st.tabs(["README", "Release notes"])

    with readme_tab:
        st.markdown(readme_text)

    with notes_tab:
        st.markdown(release_notes_text)
