from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from .session_sqlite import SQLiteSession
from .tools import Tool
from .types import Usage

TContext = TypeVar("TContext")


@dataclass
class RunContextWrapper(Generic[TContext]):
    context: TContext
    session: SQLiteSession | None = None
    usage: Usage = field(default_factory=Usage)


@dataclass
class Agent:
    name: str
    instructions: str
    model: Any
    tools: list[Tool] | None = None
    output_type: type[BaseModel] | None = None
    tool_choice_on_first_turn: str | dict[str, Any] | None = None

