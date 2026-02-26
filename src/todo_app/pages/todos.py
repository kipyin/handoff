"""Todos page implementation for the engagement to-do app."""

from __future__ import annotations

import streamlit as st

from todo_app.ui_components import _build_todo_dataframe, _render_editable_table
from todo_app.data import list_projects, query_todos


def render_todos_page() -> None:
    """Render the main todos page with a unified editable table."""
    st.subheader("Todos")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one on the Projects page.")
        return

    todos = query_todos()
    df = _build_todo_dataframe(todos, include_project=True)
    _render_editable_table(
        source_df=df,
        projects=projects,
        key_prefix="main",
        context_label="view=todos_page",
    )
