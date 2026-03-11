"""Lightweight timing instrumentation for the Now page.

Captures elapsed time for render and key action flows to support
before/after experience comparison during rollout. Local only;
no external telemetry.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from loguru import logger


@contextmanager
def time_action(name: str) -> Iterator[None]:
    """Context manager that logs elapsed time in milliseconds for a named action.

    Use for render and key action flows to support observability and
    before/after comparison during rollout.

    Args:
        name: Short label for the action (e.g. "now_render", "now_check_in").

    Yields:
        None. Logs elapsed_ms at INFO when the block exits.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("now_instrumentation {} elapsed_ms={:.1f}", name, elapsed_ms)
