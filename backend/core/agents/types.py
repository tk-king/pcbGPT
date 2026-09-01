from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


@dataclass
class Usage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    max_total_tokens: int = 0
    input_tokens_details: dict[str, Any] = field(default_factory=dict)
    output_tokens_details: dict[str, Any] = field(default_factory=dict)

    def add_openai_usage(self, usage_obj: Any | None) -> None:
        if usage_obj is None:
            return
        self.requests += 1
        input_tokens = getattr(usage_obj, "prompt_tokens", None)
        if input_tokens is None:
            input_tokens = getattr(usage_obj, "input_tokens", 0)
        output_tokens = getattr(usage_obj, "completion_tokens", None)
        if output_tokens is None:
            output_tokens = getattr(usage_obj, "output_tokens", 0)
        self.input_tokens += int(input_tokens or 0)
        self.output_tokens += int(output_tokens or 0)
        total = int(getattr(usage_obj, "total_tokens", 0) or 0)
        self.total_tokens += total
        if total > self.max_total_tokens:
            self.max_total_tokens = total

    def merge(self, other: Usage) -> None:
        self.requests += other.requests
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.total_tokens += other.total_tokens
        if other.max_total_tokens > self.max_total_tokens:
            self.max_total_tokens = other.max_total_tokens


class AgentEvent(TypedDict, total=False):
    type: Literal[
        "start",
        "llm_request",
        "llm_response",
        "assistant_delta",
        "assistant_message",
        "tool_call",
        "tool_result",
        "error",
        "done",
    ]
    session_id: str
    turn: int
    data: dict[str, Any]
