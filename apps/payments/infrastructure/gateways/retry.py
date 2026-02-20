"""Exponential-backoff retry decorator for payment gateway calls."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])


def with_retry(max_attempts: int = 3, base_delay: float = 1.0) -> Callable[[_F], _F]:
    """
    Decorator that retries a function on any exception with exponential backoff.

    Delays: base_delay, base_delay*2, base_delay*4, ... (no sleep after last attempt).

    @param max_attempts - total number of tries including the first
    @param base_delay - seconds to wait before the second attempt; doubles each retry
    @returns decorator that wraps the target function with retry logic
    """

    def decorator(func: _F) -> _F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Attempt the call up to max_attempts times, sleeping between failures."""
            last_error: BaseException | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_error = exc
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            "Gateway call failed (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1,
                            max_attempts,
                            delay,
                            exc,
                        )
                        time.sleep(delay)
            raise last_error  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
