"""Streamlit runtime options applied via environment variables.

Must be imported before any Streamlit process is started (e.g. by the launcher
that runs `python -m handoff` or `uv run handoff run`). The launcher sets
these in os.environ and spawns `streamlit run` with that env so the options
take effect. At deploy time the package is obfuscated with PyArmor.
"""

from __future__ import annotations

import os

os.environ.setdefault("STREAMLIT_CLIENT_SHOW_ERROR_DETAILS", "none")
os.environ.setdefault("STREAMLIT_CLIENT_TOOLBAR_MODE", "viewer")
os.environ.setdefault("STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION", "false")
os.environ.setdefault("STREAMLIT_CLIENT_SHOW_ERROR_LINKS", "false")
os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
