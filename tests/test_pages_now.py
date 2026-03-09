"""Tests for the Now page."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from handoff.pages.now import render_now_page


def test_render_now_page_no_projects_shows_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """When there are no projects, the Now page shows an info message."""
    st_mock = MagicMock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [])
    render_now_page()
    st_mock.info.assert_called_once()
    assert "No projects" in st_mock.info.call_args[0][0]


def test_render_now_page_with_projects_queries_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """When projects exist, the page calls query_now_items and renders results."""
    from types import SimpleNamespace

    st_mock = MagicMock()
    st_mock.multiselect.return_value = []
    st_mock.text_input.return_value = ""
    st_mock.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_helpers", lambda: ["Alice"])
    query_calls: list[dict] = []

    def capture_query(**kwargs):
        query_calls.append(kwargs)
        return []

    monkeypatch.setattr("handoff.pages.now.query_now_items", capture_query)
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kwargs: [])
    render_now_page()
    assert len(query_calls) == 1
    assert "project_ids" in query_calls[0]
    assert "helper_names" in query_calls[0]
