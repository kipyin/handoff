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


def test_time_action_yields_control_to_block() -> None:
    """time_action yields control and allows the block to execute."""
    execution_count = 0

    with patch("handoff.instrumentation.logger"), time_action("test_action"):
        execution_count += 1

    assert execution_count == 1


def test_time_action_nested_calls_log_separately() -> None:
    """Nested time_action calls log separately."""
    with (
        patch("handoff.instrumentation.logger") as mock_logger,
        patch(
            "handoff.instrumentation.time.perf_counter",
            side_effect=[1.0, 1.1, 1.15, 1.25],
        ),
        time_action("outer"),
        time_action("inner"),
    ):
        pass

    # Should have two log entries
    assert mock_logger.info.call_count == 2
    calls = mock_logger.info.call_args_list
    assert calls[0][0][1] == "inner"
    assert calls[1][0][1] == "outer"


def test_time_action_with_very_small_elapsed_time() -> None:
    """time_action handles very small elapsed times correctly."""
    with (
        patch("handoff.instrumentation.logger") as mock_logger,
        patch(
            "handoff.instrumentation.time.perf_counter",
            side_effect=[100.0, 100.0001],  # 0.1ms elapsed
        ),
        time_action("fast_action"),
    ):
        pass

    mock_logger.info.assert_called_once()
    call_args = mock_logger.info.call_args[0]
    assert "fast_action" in call_args
    # elapsed_ms should be approximately 0.1
    assert call_args[2] == pytest.approx(0.1, abs=0.05)


def test_time_action_exception_propagates_after_logging() -> None:
    """Exception raised in block propagates even after logging."""

    class CustomError(Exception):
        pass

    with (
        patch("handoff.instrumentation.logger") as mock_logger,
        pytest.raises(CustomError, match="test error"),
        time_action("failing"),
    ):
        raise CustomError("test error")

    # Verify logging happened
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args[0][1] == "failing"
