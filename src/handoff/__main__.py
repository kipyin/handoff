"""Launcher that applies Streamlit config then runs the app.

Run with: python -m handoff

This ensures STREAMLIT_* env vars are set before the Streamlit process starts
(interfaces.streamlit.runtime_config). Used by the embedded build (handoff.bat)
and can be used for dev: uv run python -m handoff
"""

from __future__ import annotations

import os
import subprocess
import sys

# Apply Streamlit config before any streamlit process is started.
import handoff.interfaces.streamlit.runtime_config  # noqa: F401

sys.exit(
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "app.py"],
        env=os.environ,
    ).returncode
)
