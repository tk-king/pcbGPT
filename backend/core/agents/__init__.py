"""Lightweight in-repo agent runtime (no external 'openai-agents' dependency).

This package intentionally provides a small surface area similar to the old
`agents` package used by this repo:

- `Agent`: agent definition (instructions, tools, model)
- `Runner`: runs agents with tool-calling and optional streaming of events
- `function_tool`: wraps a python function as an LLM tool (also works as a decorator)
- `RunContextWrapper`: passed to tools that accept a first `wrapper` argument
- `SQLiteSession`: persists a session (messages + events) to a sqlite DB
"""

from .agent import Agent, RunContextWrapper
from .runner import Runner
from .session_sqlite import SQLiteSession
from .tools import Tool, function_tool

__all__ = [
    "Agent",
    "RunContextWrapper",
    "Runner",
    "SQLiteSession",
    "Tool",
    "function_tool",
]

