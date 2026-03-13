"""Autosave wrapper for Streamlit data_editor widgets.

Provides a drop-in replacement for ``st.data_editor`` that persists changes
automatically via an ``on_change`` callback, avoiding explicit ``st.rerun()``
calls for simple cell edits and preserving cursor focus in the editor.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st
from loguru import logger


def autosave_editor(
    display_df: pd.DataFrame,
    *,
    key: str,
    persist_fn: Callable[[dict, pd.DataFrame], bool],
    **editor_kwargs: Any,
) -> pd.DataFrame:
    """Render ``st.data_editor`` with automatic persistence on change.

    Args:
        display_df: The DataFrame to display and edit.
        key: Streamlit widget key for the data_editor.
        persist_fn: ``(editor_state, prev_display_df) -> needs_rerun``.
            Called when the editor detects changes.  Should persist the
            changes to the database and return ``True`` only if a full
            ``st.rerun()`` is needed (e.g. row additions or deletions
            that change the visible row count).
        **editor_kwargs: Forwarded to ``st.data_editor``.

    Returns:
        The edited DataFrame (same as ``st.data_editor`` return value).

    """
    ctx_key = f"__{key}_autosave_ctx"
    rerun_key = f"__{key}_needs_rerun"

    def _on_change() -> None:
        state = st.session_state.get(key)
        if not state:
            return
        edited = state.get("edited_rows", {})
        added = state.get("added_rows", [])
        deleted = state.get("deleted_rows", [])
        if not (edited or added or deleted):
            return
        ctx = st.session_state.get(ctx_key)
        if ctx is None:
            logger.warning("autosave_editor: missing context for key={}", key)
            return
        needs_rerun = persist_fn(state, ctx["display_df"])
        if needs_rerun:
            st.session_state[rerun_key] = True

    # Deferred rerun: the on_change callback cannot call st.rerun()
    # directly (it's a no-op inside callbacks), so we set a flag and
    # check it here, before the next render.
    if st.session_state.pop(rerun_key, False):
        st.rerun()

    st.session_state[ctx_key] = {"display_df": display_df.copy()}

    return st.data_editor(
        display_df,
        key=key,
        on_change=_on_change,
        **editor_kwargs,
    )
