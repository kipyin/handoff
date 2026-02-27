"""Legacy Streamlit entry script for the Projects page.

This file is kept as a thin shim for classic multipage Streamlit usage when
running `streamlit run app.py` is not desired. The primary navigation for the
app is defined in `app.py` using `st.navigation`; new pages should be wired
through that entrypoint instead of adding more files under the root `pages/`
directory.
"""

from app import APP_VERSION
from todo_app.ui_facade import render_projects_page, setup


def main() -> None:
    """Render the Projects page."""
    setup(APP_VERSION)
    render_projects_page()


if __name__ == "__main__":
    main()
