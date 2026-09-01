from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RunErrorDetails:
    """Minimal compatibility shim for experiment logging."""

    input: str | list[dict[str, Any]]
    new_items: list[dict[str, Any]]
    context_wrapper: Any | None = None


class AgentsException(RuntimeError):
    def __init__(self, message: str, *, run_data: RunErrorDetails | None = None):
        super().__init__(message)
        self.run_data = run_data

