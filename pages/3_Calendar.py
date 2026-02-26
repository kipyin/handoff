"""Streamlit entry script for the Calendar page."""

from app import APP_VERSION
from todo_app.ui import render_calendar_page, setup


def main() -> None:
    """Render the Calendar page."""
    setup(APP_VERSION)
    render_calendar_page()


if __name__ == "__main__":
    main()
