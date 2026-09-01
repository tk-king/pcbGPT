"""Shared exception classes used across circuit and data layers."""

from __future__ import annotations

import contextlib
import contextvars
from typing import Iterator


class CircuitException(Exception):
    """Domain-specific error raised for invalid circuit operations."""

    pass


_circuit_error_collector: contextvars.ContextVar[list[Exception] | None] = (
    contextvars.ContextVar("circuit_error_collector", default=None)
)


@contextlib.contextmanager
def collect_circuit_errors() -> Iterator[list[Exception]]:
    errors: list[Exception] = []
    token = _circuit_error_collector.set(errors)
    try:
        yield errors
    finally:
        _circuit_error_collector.reset(token)


def record_circuit_error(exc: Exception) -> bool:
    errors = _circuit_error_collector.get()
    if errors is None:
        return False
    errors.append(exc)
    return True
