"""Per-tool-call progress reporting for long-running tools.

Tools (e.g. the datasheet processing pipeline) report progress through
:meth:`report_tool_progress`. The agent runner registers a sink for the
duration of a tool call so progress messages can be streamed to the UI as
``tool_progress`` events instead of only being printed to stdout.

A :class:`contextvars.ContextVar` keeps sinks isolated between concurrent
runs; ``asyncio.to_thread`` copies the context, so sinks registered on the
event-loop thread are also visible inside worker threads.
"""

from __future__ import annotations

import contextvars
from typing import Any, Callable

ProgressSink = Callable[[str], Any]

_sink_var: contextvars.ContextVar[ProgressSink | None] = contextvars.ContextVar(
    "tool_progress_sink", default=None
)


def set_tool_progress_sink(sink: ProgressSink | None) -> contextvars.Token:
    """Register a progress sink; returns a token for :meth:`reset_tool_progress_sink`."""
    return _sink_var.set(sink)


def reset_tool_progress_sink(token: contextvars.Token) -> None:
    try:
        _sink_var.reset(token)
    except ValueError:
        # Token from a different context; ignore.
        pass


def report_tool_progress(message: str) -> bool:
    """Forward a progress message to the active sink (if any).

    Returns True when a sink consumed the message.
    """
    sink = _sink_var.get()
    if sink is None:
        return False
    try:
        sink(message)
        return True
    except Exception:  # noqa: BLE001 - progress reporting must never break a tool
        return False
