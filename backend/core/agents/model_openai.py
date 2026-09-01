from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any


@dataclass(frozen=True)
class OpenAIChatModel:
    """Thin wrapper around an OpenAI-compatible async client."""

    client: Any
    model_name: str
    temperature: float | None = None
    reasoning_effort: str | None = None
    request_kwargs: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _status_code(exc: Exception) -> int | None:
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        response = getattr(exc, "response", None)
        response_code = getattr(response, "status_code", None)
        return response_code if isinstance(response_code, int) else None

    @staticmethod
    def _error_text(exc: Exception) -> str:
        parts: list[str] = []
        text = str(exc).strip()
        if text:
            parts.append(text)
        response = getattr(exc, "response", None)
        response_text = getattr(response, "text", None)
        if isinstance(response_text, str) and response_text.strip():
            parts.append(response_text.strip())
        body = getattr(exc, "body", None)
        if body:
            parts.append(str(body).strip())
        return " | ".join(part for part in parts if part)

    def _should_retry_without_stream_options(
        self,
        *,
        exc: Exception,
        kwargs: dict[str, Any],
    ) -> bool:
        if not kwargs.get("stream") or "stream_options" not in kwargs:
            return False
        status_code = self._status_code(exc)
        if status_code is not None and status_code != 400:
            return False
        error_text = self._error_text(exc).lower()
        if status_code == 400 and not error_text:
            return True
        return any(
            token in error_text
            for token in (
                "stream_options",
                "include_usage",
                "unknown parameter",
                "unsupported parameter",
                "extra inputs are not permitted",
                "extra fields not permitted",
                "not permitted",
                "unrecognized request argument",
            )
        )

    def _should_retry_with_responses(self, exc: Exception) -> bool:
        if self._status_code(exc) not in (400, 404):
            return False
        error_text = self._error_text(exc).lower()
        return any(
            marker in error_text
            for marker in (
                "use /v1/responses",
                "use the /v1/responses",
                "use v1/responses",
                "responses endpoint instead",
            )
        )

    @staticmethod
    def _responses_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if not tools:
            return None
        converted: list[dict[str, Any]] = []
        for tool in tools:
            if tool.get("type") != "function":
                converted.append(tool)
                continue
            function = tool.get("function") or {}
            converted.append(
                {
                    "type": "function",
                    "name": function.get("name"),
                    "description": function.get("description") or "",
                    "parameters": function.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        return converted

    @staticmethod
    def _responses_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            if message.get("role") == "tool":
                converted.append(
                    {
                        "type": "function_call_output",
                        "call_id": message.get("tool_call_id") or "",
                        "output": message.get("content") or "",
                    }
                )
                continue
            tool_calls = message.get("tool_calls")
            if message.get("role") == "assistant" and tool_calls:
                content = message.get("content")
                if content:
                    converted.append({"role": "assistant", "content": content})
                for tool_call in tool_calls:
                    function = tool_call.get("function") or {}
                    converted.append(
                        {
                            "type": "function_call",
                            "call_id": tool_call.get("id") or "",
                            "name": function.get("name") or "",
                            "arguments": function.get("arguments") or "",
                        }
                    )
                continue
            converted.append(message)
        return converted

    @staticmethod
    def _text_from_responses_message(item: Any) -> str:
        parts: list[str] = []
        for content in getattr(item, "content", None) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)

    def _chat_completion_from_response(self, response: Any) -> Any:
        content = getattr(response, "output_text", None)
        tool_calls: list[Any] = []

        for item in getattr(response, "output", None) or []:
            item_type = getattr(item, "type", None)
            if content is None and item_type == "message":
                content = self._text_from_responses_message(item)
            if item_type == "function_call":
                call_id = getattr(item, "call_id", None) or getattr(item, "id", None) or ""
                tool_calls.append(
                    SimpleNamespace(
                        id=call_id,
                        type="function",
                        function=SimpleNamespace(
                            name=getattr(item, "name", "") or "",
                            arguments=getattr(item, "arguments", "") or "",
                        ),
                    )
                )

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content or "", tool_calls=tool_calls or None))],
            usage=getattr(response, "usage", None),
        )

    @staticmethod
    def _chat_chunk(*, delta_content: str | None = None, tool_call: Any | None = None, usage: Any | None = None) -> Any:
        delta = SimpleNamespace(content=delta_content, tool_calls=[tool_call] if tool_call is not None else None)
        return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)

    async def _chat_stream_from_response_stream(self, response_stream: Any):
        function_call_arguments: dict[str, str] = {}
        function_call_names: dict[str, str] = {}
        function_call_indices: dict[str, int] = {}

        def _call_keys(event: Any, item: Any | None = None) -> list[str]:
            keys: list[str] = []
            for source in (event, item):
                if source is None:
                    continue
                for attr in ("item_id", "call_id", "id", "output_index"):
                    value = getattr(source, attr, None)
                    if value is not None:
                        keys.append(str(value))
            return keys

        def _store_for_keys(store: dict[str, str], keys: list[str], value: str, *, append: bool = False) -> None:
            if not keys or value is None:
                return
            existing = ""
            if append:
                for key in keys:
                    if key in store:
                        existing = store[key]
                        break
            next_value = f"{existing}{value}" if append else value
            for key in keys:
                store[key] = next_value

        def _lookup(store: dict[str, str], keys: list[str]) -> str:
            for key in keys:
                value = store.get(key)
                if value:
                    return value
            return ""

        def _store_index(keys: list[str], event: Any | None = None) -> int:
            for key in keys:
                if key in function_call_indices:
                    return function_call_indices[key]
            # Responses output_index counts every output item, including reasoning
            # items. Chat tool-call indices must instead be compact and zero-based.
            index = len(set(function_call_indices.values()))
            for key in keys:
                function_call_indices[key] = index
            return index

        async for event in response_stream:
            event_type = getattr(event, "type", "")
            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", None)
                if delta:
                    yield self._chat_chunk(delta_content=delta)
                continue
            if event_type == "response.output_item.added":
                item = getattr(event, "item", None)
                if getattr(item, "type", None) == "function_call":
                    keys = _call_keys(event, item)
                    _store_index(keys, event)
                    _store_for_keys(function_call_names, keys, getattr(item, "name", "") or "")
                    _store_for_keys(function_call_arguments, keys, getattr(item, "arguments", "") or "")
                continue
            if event_type == "response.function_call_arguments.delta":
                _store_for_keys(function_call_arguments, _call_keys(event), getattr(event, "delta", "") or "", append=True)
                continue
            if event_type == "response.function_call_arguments.done":
                _store_for_keys(function_call_arguments, _call_keys(event), getattr(event, "arguments", "") or "")
                continue
            if event_type == "response.output_item.done":
                item = getattr(event, "item", None)
                if getattr(item, "type", None) != "function_call":
                    continue
                call_id = getattr(item, "call_id", None) or getattr(item, "id", None) or ""
                keys = _call_keys(event, item)
                index = _store_index(keys, event)
                arguments = getattr(item, "arguments", None) or _lookup(function_call_arguments, keys)
                name = getattr(item, "name", None) or _lookup(function_call_names, keys)
                tool_call = SimpleNamespace(
                    index=index,
                    id=call_id,
                    type="function",
                    function=SimpleNamespace(
                        name=name or "",
                        arguments=arguments or "",
                    ),
                )
                yield self._chat_chunk(tool_call=tool_call)
                continue
            if event_type == "response.completed":
                response = getattr(event, "response", None)
                usage = getattr(response, "usage", None)
                if usage is not None:
                    yield self._chat_chunk(usage=usage)

    def _responses_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        responses_kwargs: dict[str, Any] = {
            "model": kwargs["model"],
            "input": self._responses_input(kwargs["messages"]),
        }
        if kwargs.get("stream"):
            responses_kwargs["stream"] = True
        tools = self._responses_tools(kwargs.get("tools"))
        if tools:
            responses_kwargs["tools"] = tools
            responses_kwargs["tool_choice"] = kwargs.get("tool_choice", "auto")
        if kwargs.get("response_format"):
            responses_kwargs["text"] = {"format": kwargs["response_format"]}
        if "temperature" in kwargs:
            responses_kwargs["temperature"] = kwargs["temperature"]
        if kwargs.get("reasoning_effort"):
            responses_kwargs["reasoning"] = {"effort": kwargs["reasoning_effort"]}
        elif kwargs.get("reasoning"):
            responses_kwargs["reasoning"] = kwargs["reasoning"]
        if kwargs.get("verbosity"):
            responses_kwargs.setdefault("text", {})["verbosity"] = kwargs["verbosity"]
        for key in (
            "background",
            "include",
            "max_output_tokens",
            "metadata",
            "parallel_tool_calls",
            "prompt_cache_key",
            "prompt_cache_retention",
            "safety_identifier",
            "service_tier",
            "store",
            "top_p",
            "truncation",
        ):
            if key in kwargs:
                responses_kwargs[key] = kwargs[key]
        return responses_kwargs

    def _apply_request_kwargs(self, kwargs: dict[str, Any]) -> None:
        for key, value in self.request_kwargs.items():
            if value is None:
                kwargs.pop(key, None)
            else:
                kwargs[key] = value

    async def _create_with_compat_fallback(self, **kwargs: Any) -> Any:
        try:
            return await self.client.chat.completions.create(**kwargs)
        except Exception as exc:
            if self._should_retry_with_responses(exc):
                response = await self.client.responses.create(**self._responses_kwargs(**kwargs))
                if kwargs.get("stream"):
                    return self._chat_stream_from_response_stream(response)
                return self._chat_completion_from_response(response)
            if not self._should_retry_without_stream_options(exc=exc, kwargs=kwargs):
                raise
            retry_kwargs = dict(kwargs)
            retry_kwargs.pop("stream_options", None)
            try:
                return await self.client.chat.completions.create(**retry_kwargs)
            except Exception as retry_exc:
                if not self._should_retry_with_responses(retry_exc):
                    raise
                response = await self.client.responses.create(**self._responses_kwargs(**retry_kwargs))
                if retry_kwargs.get("stream"):
                    return self._chat_stream_from_response_stream(response)
                return self._chat_completion_from_response(response)

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {"model": self.model_name, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"
        if response_format:
            kwargs["response_format"] = response_format
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            kwargs["reasoning_effort"] = self.reasoning_effort
        self._apply_request_kwargs(kwargs)
        return await self._create_with_compat_fallback(**kwargs)

    async def stream(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ):
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"
        if response_format:
            kwargs["response_format"] = response_format
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.reasoning_effort is not None:
            kwargs["reasoning_effort"] = self.reasoning_effort
        self._apply_request_kwargs(kwargs)
        return await self._create_with_compat_fallback(**kwargs)
