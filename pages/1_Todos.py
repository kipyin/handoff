"""Streamlit entry script for the Todos page."""

from app import APP_VERSION
from todo_app.ui import render_todos_page, setup


def main() -> None:
    """Render the Todos page."""
    setup(APP_VERSION)
    render_todos_page()


if __name__ == "__main__":
    main()
