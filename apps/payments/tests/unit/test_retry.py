"""Unit tests for the gateway retry decorator."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from apps.payments.infrastructure.gateways.retry import with_retry


class _SomeError(Exception):
    """Sentinel error for retry tests."""


def test_retry_succeeds_on_first_attempt():
    """Function that succeeds immediately returns its result without retrying."""
    func = MagicMock(return_value="ok")
    wrapped = with_retry(max_attempts=3, base_delay=0.0)(func)

    result = wrapped("a", b=1)

    assert result == "ok"
    func.assert_called_once_with("a", b=1)


def test_retry_succeeds_after_two_failures():
    """Function that fails twice then succeeds returns the successful result."""
    func = MagicMock(side_effect=[_SomeError("fail1"), _SomeError("fail2"), "ok"])
    wrapped = with_retry(max_attempts=3, base_delay=0.0)(func)

    result = wrapped()

    assert result == "ok"
    assert func.call_count == 3


def test_retry_raises_last_error_after_max_attempts():
    """After exhausting all attempts the last exception is re-raised."""
    func = MagicMock(side_effect=_SomeError("always fails"))
    wrapped = with_retry(max_attempts=3, base_delay=0.0)(func)

    with pytest.raises(_SomeError, match="always fails"):
        wrapped()

    assert func.call_count == 3


def test_retry_sleeps_with_exponential_backoff():
    """Delay between attempts doubles each time: base, base*2, ... (no sleep after last)."""
    func = MagicMock(side_effect=[_SomeError("e1"), _SomeError("e2"), "ok"])

    with patch("apps.payments.infrastructure.gateways.retry.time.sleep") as mock_sleep:
        wrapped = with_retry(max_attempts=3, base_delay=1.0)(func)
        wrapped()

    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list == [call(1.0), call(2.0)]


def test_retry_does_not_sleep_after_last_failure():
    """No sleep after the final failing attempt."""
    func = MagicMock(side_effect=_SomeError("fail"))

    with patch("apps.payments.infrastructure.gateways.retry.time.sleep") as mock_sleep:
        wrapped = with_retry(max_attempts=2, base_delay=1.0)(func)
        with pytest.raises(_SomeError):
            wrapped()

    # only 1 sleep between attempt 1 and attempt 2; none after attempt 2
    assert mock_sleep.call_count == 1
