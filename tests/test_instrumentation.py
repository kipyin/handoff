"""Tests for the instrumentation module."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from handoff.instrumentation import time_action


def test_time_action_logs_elapsed_ms() -> None:
    """time_action logs elapsed time in milliseconds when the block completes."""
    with patch("handoff.instrumentation.logger") as mock_logger:
        with time_action("test_action"):
            time.sleep(0.02)  # 20ms minimum for reliable assertion

        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args
        assert args[0][0] == "now_instrumentation {} elapsed_ms={:.1f}"
        assert args[0][1] == "test_action"
        elapsed_ms = args[0][2]
        assert elapsed_ms >= 18  # Allow some variance


def test_time_action_logs_even_on_exception() -> None:
    """time_action logs elapsed time when the block raises."""
    with (
        patch("handoff.instrumentation.logger") as mock_logger,
        pytest.raises(ValueError, match="oops"),
    ):
        with time_action("failing_action"):
            time.sleep(0.01)
            raise ValueError("oops")

    mock_logger.info.assert_called_once()
    args = mock_logger.info.call_args
    assert args[0][1] == "failing_action"
    assert args[0][2] >= 9
