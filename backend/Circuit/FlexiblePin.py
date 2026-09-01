from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.Circuit.Pin import Pin
from backend.core.exceptions import CircuitException


@dataclass(frozen=True)
class FlexiblePin:
    actual: Pin
    alternatives: tuple[Pin, ...] = ()

    def __init__(self, actual: Pin, alternatives: Iterable[Pin] | None = None):
        alts = tuple(alternatives or ())
        if any(not isinstance(pin, Pin) for pin in alts):
            raise CircuitException("FlexiblePin alternatives must be Pin instances.")
        if not isinstance(actual, Pin):
            raise CircuitException("FlexiblePin actual must be a Pin instance.")
        object.__setattr__(self, "actual", actual)
        object.__setattr__(self, "alternatives", alts)

    def __rand__(self, other):
        return other & self
