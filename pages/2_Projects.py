"""Streamlit entry script for the Projects page."""

from app import APP_VERSION
from todo_app.ui_facade import render_projects_page, setup


def main() -> None:
    """Render the Projects page."""
    setup(APP_VERSION)
    render_projects_page()


if __name__ == "__main__":
    main()
