"""Tests for the instrumentation module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from handoff.instrumentation import time_action


def test_time_action_logs_elapsed_ms() -> None:
    """time_action logs elapsed time in milliseconds when the block completes."""
    with (
        patch("handoff.instrumentation.logger") as mock_logger,
        patch(
            "handoff.instrumentation.time.perf_counter",
            side_effect=[1.0, 1.123],
        ),
        time_action("test_action"),
    ):
        pass

    mock_logger.info.assert_called_once()
    args = mock_logger.info.call_args
    assert args[0][0] == "now_instrumentation {} elapsed_ms={:.1f}"
    assert args[0][1] == "test_action"
    assert args[0][2] == pytest.approx(123.0)


def test_time_action_logs_even_on_exception() -> None:
    """time_action logs elapsed time when the block raises."""
    with (
        patch("handoff.instrumentation.logger") as mock_logger,
        patch(
            "handoff.instrumentation.time.perf_counter",
            side_effect=[10.0, 10.045],
        ),
        pytest.raises(ValueError, match="oops"),
        time_action("failing_action"),
    ):
        raise ValueError("oops")

    mock_logger.info.assert_called_once()
    args = mock_logger.info.call_args
    assert args[0][1] == "failing_action"
    assert args[0][2] == pytest.approx(45.0)
