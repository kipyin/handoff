"""Tests for the top-level Streamlit app entrypoint."""

from __future__ import annotations


def test_page_wrapper_uses_renderer_name_and_calls_setup(monkeypatch) -> None:
    """Each wrapped page keeps a unique function name for Streamlit routing."""
    import app

    calls: list[str] = []

    def first_page() -> None:
        """First page docstring."""
        calls.append("first")

    monkeypatch.setattr(app, "setup", lambda version: calls.append(version))
    wrapped = app._page(first_page)

    assert wrapped.__name__ == "first_page"
    assert wrapped.__wrapped__ is first_page
    assert wrapped.__doc__ == "First page docstring."

    wrapped()
    assert calls == [app.APP_VERSION, "first"]
